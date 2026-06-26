"""Machine-readable result writers (FR-029).

Aggregate JSON + per-document JSONL + the aggregate CSVs (detection, restoration,
latency). The aggregate report is originals-free (publishable); ``per_document.jsonl``
may embed originals and is therefore written to the (sensitive) results directory. The
leaks CSV (US2) redacts the value column for ``source="real"`` documents.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .result_models import AggregateResult, PerDocumentResult


def write_all(
    results_dir: Path,
    aggregate: AggregateResult,
    per_document: list[PerDocumentResult],
) -> list[Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    aggregate_path = results_dir / "aggregate.json"
    aggregate_path.write_text(aggregate.model_dump_json(indent=2), encoding="utf-8")
    written.append(aggregate_path)

    per_document_path = results_dir / "per_document.jsonl"
    per_document_path.write_text(
        "\n".join(document.model_dump_json() for document in per_document) + "\n",
        encoding="utf-8",
    )
    written.append(per_document_path)

    written.append(_write_detection_csv(results_dir, aggregate))
    written.append(_write_restoration_csv(results_dir, aggregate))
    written.append(_write_latency_csv(results_dir, aggregate))
    leaks_path = _write_leaks_csv(results_dir, aggregate, per_document)
    if leaks_path is not None:
        written.append(leaks_path)
    return written


def _write_detection_csv(results_dir: Path, aggregate: AggregateResult) -> Path:
    path = results_dir / "detection_per_type.csv"
    overlap = {
        m.type: m
        for m in (
            aggregate.detection_overlap.per_type if aggregate.detection_overlap else []
        )
    }
    exact = {
        m.type: m
        for m in (
            aggregate.detection_exact.per_type if aggregate.detection_exact else []
        )
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        # Recall-first column order (Constitution II / FR-018).
        writer.writerow(
            [
                "type",
                "support",
                "recall_overlap",
                "precision_overlap",
                "f1_overlap",
                "tp_overlap",
                "fp_overlap",
                "fn_overlap",
                "recall_exact",
                "precision_exact",
                "f1_exact",
            ]
        )
        for entity_type in sorted(overlap):
            over = overlap[entity_type]
            strict = exact.get(entity_type)
            writer.writerow(
                [
                    entity_type,
                    over.support,
                    over.recall,
                    over.precision,
                    over.f1,
                    over.tp,
                    over.fp,
                    over.fn,
                    strict.recall if strict else "",
                    strict.precision if strict else "",
                    strict.f1 if strict else "",
                ]
            )
    return path


def _write_restoration_csv(results_dir: Path, aggregate: AggregateResult) -> Path:
    path = results_dir / "restoration.csv"
    restoration = aggregate.restoration
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scope", "outcome", "count"])
        if restoration:
            for outcome, count in sorted(restoration.by_outcome.items()):
                writer.writerow(["__all__", outcome, count])
            for entity_type, counts in sorted(restoration.by_type.items()):
                for outcome, count in sorted(counts.items()):
                    writer.writerow([entity_type, outcome, count])
            writer.writerow(
                ["__doc_exact_restore_rate__", "", restoration.doc_exact_restore_rate]
            )
    return path


def _write_latency_csv(results_dir: Path, aggregate: AggregateResult) -> Path:
    path = results_dir / "latency.csv"
    latency = aggregate.latency
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["grouping", "bucket", "channel", "p50", "p90", "p99", "mean", "n"]
        )
        if latency:
            for channel, stats in sorted(latency.by_channel.items()):
                writer.writerow(
                    [
                        "overall",
                        "",
                        channel,
                        stats.p50,
                        stats.p90,
                        stats.p99,
                        stats.mean,
                        stats.n,
                    ]
                )
            for grouping, name in (
                (latency.by_length_bucket, "length"),
                (latency.by_entity_bucket, "entity_count"),
            ):
                for bucket, channels in sorted(grouping.items()):
                    for channel, stats in sorted(channels.items()):
                        writer.writerow(
                            [
                                name,
                                bucket,
                                channel,
                                stats.p50,
                                stats.p90,
                                stats.p99,
                                stats.mean,
                                stats.n,
                            ]
                        )
    return path


def _write_leaks_csv(
    results_dir: Path,
    aggregate: AggregateResult,
    per_document: list[PerDocumentResult],
) -> Path | None:
    if aggregate.leak is None:
        return None
    real_doc_ids = {d.doc_id for d in per_document if d.source == "real"}
    path = results_dir / "leaks.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["doc_id", "type", "value", "form_found", "match_mode", "start", "end"]
        )
        for finding in aggregate.leak.findings:
            redacted = finding.doc_id in real_doc_ids
            writer.writerow(
                [
                    finding.doc_id,
                    finding.type,
                    "[REDACTED]" if redacted else finding.original,
                    "[REDACTED]" if redacted else finding.form_found,
                    finding.match_mode,
                    finding.start,
                    finding.end,
                ]
            )
    return path
