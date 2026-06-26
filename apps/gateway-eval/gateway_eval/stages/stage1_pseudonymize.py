"""Stage 1 — pseudonymization correctness, no LLM (FR-015).

Per document: detect → pseudonymize → depseudonymize, with a fresh session deleted
afterwards (keeps Redis clean, preserves TTL semantics). Gathers the raw materials the
scorers need (detected spans, outbound text, restored text) plus wall-clock latency per
endpoint. Scoring (detection / leak / restoration) happens in ``run_evaluation`` — this
module only drives the gateway and times it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from ..config import EvaluationConfig
from ..corpus.gold_standard import GoldDocument
from ..gateway_client.evaluation_client import DetectedSpan, GatewayClientError
from ..latency.timing_collector import make_sample
from ..reporting.result_models import LatencySample


@dataclass
class Stage1Outcome:
    doc_id: str
    detected_spans: list[DetectedSpan] = field(default_factory=list)
    pseudonymized_text: str = ""
    fake_values: list[str] = field(default_factory=list)
    restored_text: str = ""
    latency: list[LatencySample] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def run_stage1(
    client, document: GoldDocument, config: EvaluationConfig
) -> Stage1Outcome:
    session_id = uuid.uuid4().hex
    outcome = Stage1Outcome(doc_id=document.doc_id)
    entity_count = len(document.entities)
    doc_length = len(document.text)

    def record(channel: str, started: float) -> None:
        outcome.latency.append(
            make_sample(
                doc_id=document.doc_id,
                stage=1,
                channel=channel,
                ms=(time.perf_counter() - started) * 1000,
                doc_length=doc_length,
                entity_count=entity_count,
                length_edges=config.length_buckets,
                entity_count_edges=config.entity_count_buckets,
            )
        )

    try:
        started = time.perf_counter()
        outcome.detected_spans = await client.detect(document.text)
        record("detect", started)

        started = time.perf_counter()
        pseudonymized = await client.pseudonymize(document.text, session_id)
        record("pseudonymize", started)
        outcome.pseudonymized_text = pseudonymized.pseudonymized_text
        outcome.fake_values = pseudonymized.fake_values

        started = time.perf_counter()
        restored = await client.depseudonymize(
            pseudonymized.pseudonymized_text, session_id
        )
        record("depseudonymize", started)
        outcome.restored_text = restored.restored_text
    except GatewayClientError as gateway_error:
        outcome.errors.append(f"stage1: {gateway_error}")
    finally:
        await client.delete_session(session_id)

    return outcome
