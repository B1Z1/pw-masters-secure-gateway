"""AnonymizationPipeline round-trip + multi-turn determinism (US1, US2).

Uses the network-free EchoProvider and a fakeredis-backed store so the whole
inbound → LLM → outbound flow runs offline (FR-027).
"""

from __future__ import annotations

from gateway_api.llm_providers.base import ChatMessage
from gateway_api.llm_providers.echo_provider import EchoProvider
from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pipeline.anonymization_pipeline import AnonymizationPipeline


class _FakeEngine:
    """Detect by literal substring lookup — no spaCy needed."""

    def __init__(self, specs):
        # specs: list of (entity_type, value, lemma, case, metadata)
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


async def test_round_trip_hides_pii_and_restores(make_store):
    store = make_store(seed=7)
    engine = _FakeEngine(
        [
            ("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {}),
            ("LOCATION", "Kraków", "Kraków", "nom", {}),
            ("PESEL", "90010112345", None, None, {"gender": "male"}),
        ]
    )
    pipeline = AnonymizationPipeline(engine, store)

    messages = [
        ChatMessage(role="user", content="Jan Kowalski, Kraków, PESEL 90010112345.")
    ]
    fake_messages = (await pipeline.run_inbound("s1", messages)).fake_messages

    # The provider only ever sees synthetic data (SC-001, Constitution I).
    sent = fake_messages[0].content
    assert "Jan Kowalski" not in sent
    assert "Kraków" not in sent
    assert "90010112345" not in sent

    fake_answer = (await EchoProvider().complete(fake_messages, model="stub")).content
    restored = await pipeline.depseudonymize_text("s1", fake_answer)

    assert "Jan Kowalski" in restored
    assert "Kraków" in restored
    assert "90010112345" in restored


async def test_multi_turn_repseudonymizes_whole_history_consistently(make_store):
    store = make_store(seed=7)
    engine = _FakeEngine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    pipeline = AnonymizationPipeline(engine, store)

    # Turn 2 resends an earlier assistant message that (post-display) holds the
    # original PII — every message must be pseudonymized, not only the last.
    history = [
        ChatMessage(role="user", content="Kto to Jan Kowalski?"),
        ChatMessage(role="assistant", content="Jan Kowalski to najemca."),
        ChatMessage(role="user", content="Gdzie mieszka Jan Kowalski?"),
    ]
    fake_messages = (await pipeline.run_inbound("s2", history)).fake_messages

    for message in fake_messages:
        assert "Jan Kowalski" not in message.content

    mappings = await store.get_all_mappings("s2")
    fake = next(m["fake"] for m in mappings if m["original"] == "Jan Kowalski")

    # Deterministic: the same fake in every message (FR-006 session consistency).
    assert all(fake in message.content for message in fake_messages)
