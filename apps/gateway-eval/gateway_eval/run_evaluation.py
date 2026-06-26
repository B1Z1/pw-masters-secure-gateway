"""Evaluation orchestration: health-gate → load corpus → run stage(s) → score → report.

Stage 1 produces detection (overlap + exact), restoration, and wall-clock latency.
The leak audit (US2) and Stage 2 (US4) extend this module. Ground truth is the gold
standard only — scoring never consults gateway output as the answer key (D1).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .config import EvaluationConfig
from .corpus.gold_standard import GoldDocument, corpus_stats, load_corpus
from .gateway_client.evaluation_client import EvaluationClient
from .latency.timing_collector import aggregate_latency, stage2_samples
from .reporting.result_models import (
    AggregateResult,
    CorpusStats,
    DetectionReport,
    LatencySample,
    LeakFinding,
    PerDocumentResult,
    RestorationDetail,
    RunConfigSnapshot,
    Stage2Result,
)
from .scoring import detection_metrics, leak_audit, restoration_metrics
from .scoring.surface_matching import fold_diacritics, normalize
from .stages.stage1_pseudonymize import run_stage1
from .stages.stage2_chat_flow import run_stage2

EXIT_OK = 0
EXIT_LEAK = 1
EXIT_CANNOT_RUN = 2


@dataclass
class RunResult:
    exit_code: int
    aggregate: AggregateResult | None = None
    per_document: list[PerDocumentResult] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    health: dict | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def corpus_version_hash(documents: list[GoldDocument]) -> str:
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda doc: doc.doc_id):
        digest.update(document.doc_id.encode("utf-8"))
        digest.update(document.text.encode("utf-8"))
        digest.update(str(len(document.entities)).encode("utf-8"))
    return digest.hexdigest()[:16]


async def run_evaluation(config: EvaluationConfig, client=None) -> RunResult:
    own_client = client is None
    if own_client:
        client = EvaluationClient(
            config.base_url,
            timeout_s=config.request_timeout_s,
            max_retries=config.max_retries,
        )

    async with client as gateway:
        health = await gateway.health()
        if not health.is_ok:
            return RunResult(
                exit_code=EXIT_CANNOT_RUN,
                messages=[
                    f"gateway not healthy: {health.status} {health.dependencies}"
                ],
                health=health.model_dump(),
            )

        try:
            documents = load_corpus(config.corpus_path, config.real_corpus_path)
        except (ValueError, OSError) as load_error:
            return RunResult(
                exit_code=EXIT_CANNOT_RUN,
                messages=[f"corpus load failed: {load_error}"],
                health=health.model_dump(),
            )
        if not documents:
            return RunResult(
                exit_code=EXIT_CANNOT_RUN,
                messages=[f"no documents found under {config.corpus_path}"],
                health=health.model_dump(),
            )

        started_at = _now()
        per_document: list[PerDocumentResult] = []
        overlap_reports: list[DetectionReport] = []
        exact_reports: list[DetectionReport] = []
        restoration_by_doc: dict[str, list[RestorationDetail]] = {}
        latency_samples: list[LatencySample] = []
        all_leaks: list[LeakFinding] = []
        messages: list[str] = []

        stage2_documents = 0
        stage2_leak_free = 0
        stage2_answer_restored = 0

        for document in documents:
            document_result = await _evaluate_document(
                gateway, document, config, overlap_reports, exact_reports
            )
            per_document.append(document_result)
            latency_samples.extend(document_result.latency)
            restoration_by_doc[document.doc_id] = document_result.restoration
            all_leaks.extend(document_result.leaks)
            if document_result.stage2 is not None:
                stage2_documents += 1
                stage2_leak_free += int(document_result.stage2.leak_free)
                stage2_answer_restored += int(document_result.stage2.answer_restored)

        stats = corpus_stats(documents)
        messages.extend(_target_warnings(stats))
        leak_report = leak_audit.aggregate_leaks(all_leaks)
        stage2_summary = (
            {
                "n_docs": stage2_documents,
                "n_leak_free": stage2_leak_free,
                "n_answer_restored": stage2_answer_restored,
            }
            if config.stage_two_enabled
            else None
        )

        aggregate = AggregateResult(
            config=RunConfigSnapshot(
                seed=config.seed,
                base_url=config.base_url,
                gateway_health=health.model_dump(),
                corpus_version_hash=corpus_version_hash(documents),
                span_policy="exact" if config.strict_spans else "overlap",
                provider=config.provider,
                started_at=started_at,
                finished_at=_now(),
            ),
            corpus_stats=CorpusStats(
                n_docs=stats["n_docs"],
                n_entities=stats["n_entities"],
                by_type=stats["by_type"],
                by_source=stats["by_source"],
                synthetic_ratio=stats["synthetic_ratio"],
                all_types_present=stats["all_types_present"],
            ),
            detection_overlap=(
                detection_metrics.combine_reports(overlap_reports, "overlap")
                if overlap_reports
                else None
            ),
            detection_exact=(
                detection_metrics.combine_reports(exact_reports, "exact")
                if exact_reports
                else None
            ),
            restoration=(
                restoration_metrics.aggregate_restoration(restoration_by_doc)
                if config.stage_one_enabled
                else None
            ),
            latency=aggregate_latency(latency_samples),
            leak=leak_report,
            stage2_summary=stage2_summary,
        )

        # A surviving original PII value (incl. inflected) fails the run (FR-021).
        exit_code = EXIT_OK if leak_report.passed else EXIT_LEAK
        return RunResult(
            exit_code=exit_code,
            aggregate=aggregate,
            per_document=per_document,
            messages=messages,
            health=health.model_dump(),
        )


async def _evaluate_document(
    gateway,
    document: GoldDocument,
    config: EvaluationConfig,
    overlap_reports: list[DetectionReport],
    exact_reports: list[DetectionReport],
) -> PerDocumentResult:
    result = PerDocumentResult(
        doc_id=document.doc_id,
        source=document.source,
        contract_type=document.contract_type,
        n_gold_entities=len(document.entities),
    )

    stage1_leaks: list[LeakFinding] = []
    if config.stage_one_enabled:
        outcome = await run_stage1(gateway, document, config)
        overlap = detection_metrics.build_detection_report(
            document.entities, outcome.detected_spans, "overlap"
        )
        exact = detection_metrics.build_detection_report(
            document.entities, outcome.detected_spans, "exact"
        )
        overlap_reports.append(overlap)
        exact_reports.append(exact)
        stage1_leaks = leak_audit.audit_document(
            document, outcome.pseudonymized_text, tuple(outcome.fake_values)
        )

        result.detection_overlap = overlap
        result.detection_exact = exact
        result.false_negatives, result.false_positives = detection_metrics.error_spans(
            document.entities, outcome.detected_spans, "overlap"
        )
        result.restoration = restoration_metrics.build_restoration_details(
            document, outcome.restored_text
        )
        result.latency.extend(outcome.latency)
        result.errors.extend(outcome.errors)

    stage2_leaks: list[LeakFinding] = []
    if config.stage_two_enabled:
        outcome2 = await run_stage2(gateway, document, config)
        stage2_leaks = leak_audit.audit_document(
            document, outcome2.pseudonymized_content, tuple(outcome2.fake_values)
        )
        result.stage2 = Stage2Result(
            leak_free=not stage2_leaks,
            answer_restored=_answer_reconstructs(document, outcome2.answer),
            timing_ms=outcome2.timing_ms,
        )
        result.latency.extend(
            stage2_samples(
                doc_id=document.doc_id,
                timing_ms=outcome2.timing_ms,
                doc_length=len(document.text),
                entity_count=len(document.entities),
                length_edges=config.length_buckets,
                entity_count_edges=config.entity_count_buckets,
            )
        )
        result.errors.extend(outcome2.errors)

    # Stage 1 is the authoritative leak audit; fall back to Stage 2's when only it ran.
    result.leaks = stage1_leaks if config.stage_one_enabled else stage2_leaks
    return result


def _answer_reconstructs(document: GoldDocument, answer: str) -> bool:
    """True when every gold original reappears in the de-pseudonymized answer."""
    if not answer:
        return False
    normalized_answer = normalize(answer)
    folded_answer = fold_diacritics(answer)
    for entity in document.entities:
        if (
            normalize(entity.text) not in normalized_answer
            and fold_diacritics(entity.text) not in folded_answer
        ):
            return False
    return True


def _target_warnings(stats: dict) -> list[str]:
    warnings: list[str] = []
    if stats["n_docs"] < 50:
        warnings.append(f"corpus has {stats['n_docs']} docs (< 50 target)")
    if stats["n_entities"] < 500:
        warnings.append(f"corpus has {stats['n_entities']} entities (< 500 target)")
    if not stats["all_types_present"]:
        warnings.append("not all 10 canonical entity types are represented")
    return warnings
