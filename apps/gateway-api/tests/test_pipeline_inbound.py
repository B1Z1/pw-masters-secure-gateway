"""AnonymizationPipeline.run_inbound — entities over history, last-message
replacements, and inbound stage timing (Epic 6, US1, FR-005/FR-006/FR-015)."""

from __future__ import annotations

from gateway_api.llm_providers.base import ChatMessage
from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pipeline.anonymization_pipeline import AnonymizationPipeline


class _FakeEngine:
    def __init__(self, specs):
        self._specs = specs

    def detect(self, text):
        results = []
        for entity_type, value, lemma, case, metadata in self._specs:
            start = text.find(value)
            if start != -1:
                results.append(
                    DetectedEntity(
                        entity_type=entity_type,
                        start=start,
                        end=start + len(value),
                        score=1.0,
                        text=value,
                        lemma=lemma,
                        case=case,
                        metadata=metadata or {},
                    )
                )
        return results


async def test_entities_detected_summed_over_whole_history(make_store):
    store = make_store(seed=7)
    engine = _FakeEngine(
        [
            ("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {}),
            ("PESEL", "90010112345", None, None, {"gender": "male"}),
        ]
    )
    pipeline = AnonymizationPipeline(engine, store)

    # "Jan Kowalski" appears in two messages → counted per occurrence per message.
    history = [
        ChatMessage(role="user", content="Kto to Jan Kowalski?"),
        ChatMessage(role="assistant", content="Jan Kowalski to najemca."),
        ChatMessage(role="user", content="PESEL 90010112345, Jan Kowalski?"),
    ]
    result = await pipeline.run_inbound("hist", history)

    assert result.entities_detected == {"PERSON": 3, "PESEL": 1}
    assert result.total_entities == 4


async def test_input_anonymization_is_last_user_message_only(make_store):
    store = make_store(seed=7)
    engine = _FakeEngine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    pipeline = AnonymizationPipeline(engine, store)

    history = [
        ChatMessage(role="user", content="Kto to Jan Kowalski?"),
        ChatMessage(role="assistant", content="odpowiedź"),
        ChatMessage(role="user", content="A gdzie mieszka Jan Kowalski?"),
    ]
    result = await pipeline.run_inbound("last", history)

    # Replacements describe ONLY the latest user message; offsets index its original.
    assert len(result.last_user_replacements) == 1
    replacement = result.last_user_replacements[0]
    assert replacement.original == "Jan Kowalski"
    original = "A gdzie mieszka Jan Kowalski?"
    assert original[replacement.start : replacement.end] == "Jan Kowalski"
    # The synthetic latest message contains the fake, not the original.
    assert "Jan Kowalski" not in result.last_user_pseudonymized
    assert replacement.fake in result.last_user_pseudonymized


async def test_inbound_timing_stages_present_and_non_negative(make_store):
    store = make_store(seed=7)
    engine = _FakeEngine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    pipeline = AnonymizationPipeline(engine, store)

    result = await pipeline.run_inbound(
        "t", [ChatMessage(role="user", content="Jan Kowalski")]
    )

    timing = result.timing
    assert timing.ner_analysis_ms >= 0.0
    assert timing.fake_generation_ms >= 0.0
    assert timing.redis_write_ms >= 0.0
    # PII was detected, so something was persisted to Redis.
    assert timing.redis_write_ms > 0.0


async def test_no_pii_yields_empty_counts_and_replacements(make_store):
    store = make_store(seed=7)
    pipeline = AnonymizationPipeline(_FakeEngine([]), store)

    result = await pipeline.run_inbound(
        "empty", [ChatMessage(role="user", content="cześć")]
    )

    assert result.entities_detected == {}
    assert result.total_entities == 0
    assert result.last_user_replacements == []
    assert result.last_user_pseudonymized == "cześć"
