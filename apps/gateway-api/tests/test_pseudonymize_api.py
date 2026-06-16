"""Substitution endpoints: round-trip, session, gating, no-PII logs (T011/T039)."""

from __future__ import annotations

import logging

import pytest

from gateway_api.pii_detection.dto import DetectedEntity


class _FakeEngine:
    def __init__(self, entities):
        self._entities = entities

    def detect(self, text):
        return [e.model_copy() for e in self._entities]


@pytest.fixture
def pipeline(monkeypatch, make_store):
    """Patch the gate, model readiness and the store with in-memory doubles."""
    store = make_store(seed=7)

    async def _redis_ok():
        return "ok"

    monkeypatch.setattr("gateway_api.main.check_redis", _redis_ok)
    monkeypatch.setattr("gateway_api.api.pseudonymize.get_mapping_store", lambda: store)
    monkeypatch.setattr("gateway_api.pii_detection.nlp.is_model_ready", lambda: True)

    def _set_entities(entities):
        monkeypatch.setattr(
            "gateway_api.api.pseudonymize.get_engine", lambda: _FakeEngine(entities)
        )

    return _set_entities


async def test_round_trip_restores_original(client, pipeline):
    text = "Jan Kowalski, PESEL 90010112345."
    pipeline(
        [
            DetectedEntity(
                entity_type="PERSON",
                start=0,
                end=12,
                score=1.0,
                text="Jan Kowalski",
                lemma="Jan Kowalski",
                case="nom",
            ),
            DetectedEntity(
                entity_type="PESEL",
                start=20,
                end=31,
                score=1.0,
                text="90010112345",
                metadata={"gender": "male"},
            ),
        ]
    )

    resp = await client.post("/v1/pseudonymize", json={"text": text})
    assert resp.status_code == 200
    body = resp.json()
    assert "Jan Kowalski" not in body["pseudonymized_text"]
    assert "90010112345" not in body["pseudonymized_text"]
    assert len(body["entities_replaced"]) == 2
    assert body["session_id"]

    back = await client.post(
        "/v1/depseudonymize",
        json={"text": body["pseudonymized_text"], "session_id": body["session_id"]},
    )
    assert back.json()["restored_text"] == text


async def test_session_created_when_absent(client, pipeline):
    pipeline([])
    resp = await client.post("/v1/pseudonymize", json={"text": "tekst bez PII"})
    assert resp.status_code == 200
    assert resp.json()["session_id"]


async def test_empty_input_empty_result(client, pipeline):
    pipeline([])
    resp = await client.post("/v1/pseudonymize", json={"text": ""})
    body = resp.json()
    assert body["pseudonymized_text"] == ""
    assert body["entities_replaced"] == []
    assert body["session_id"]


async def test_inflected_round_trip(client, pipeline):
    text = "Sprawa Jana Kowalskiego"
    pipeline(
        [
            DetectedEntity(
                entity_type="PERSON",
                start=7,
                end=23,
                score=1.0,
                text="Jana Kowalskiego",
                lemma="Jan Kowalski",
                case="gen",
            ),
        ]
    )
    resp = await client.post("/v1/pseudonymize", json={"text": text})
    body = resp.json()
    assert "Jana Kowalskiego" not in body["pseudonymized_text"]

    back = await client.post(
        "/v1/depseudonymize",
        json={"text": body["pseudonymized_text"], "session_id": body["session_id"]},
    )
    assert back.json()["restored_text"] == text


async def test_list_mappings_endpoint(client, pipeline):
    pipeline(
        [
            DetectedEntity(
                entity_type="PESEL",
                start=0,
                end=11,
                score=1.0,
                text="90010112345",
                metadata={"gender": "male"},
            ),
        ]
    )
    created = await client.post("/v1/pseudonymize", json={"text": "90010112345"})
    sid = created.json()["session_id"]
    listed = await client.get(f"/v1/sessions/{sid}/mappings")
    assert listed.status_code == 200
    mappings = listed.json()["mappings"]
    assert mappings and mappings[0]["original"] == "90010112345"


async def test_redis_down_returns_503(client, monkeypatch):
    async def _redis_down():
        return "unavailable"

    monkeypatch.setattr("gateway_api.main.check_redis", _redis_down)
    resp = await client.post("/v1/pseudonymize", json={"text": "Jan Kowalski"})
    assert resp.status_code == 503


async def test_no_pii_in_logs(client, pipeline, caplog):
    pipeline(
        [
            DetectedEntity(
                entity_type="PERSON",
                start=0,
                end=12,
                score=1.0,
                text="Jan Kowalski",
                lemma="Jan Kowalski",
                case="nom",
            ),
        ]
    )
    with caplog.at_level(logging.INFO, logger="gateway_api"):
        await client.post("/v1/pseudonymize", json={"text": "Jan Kowalski"})
    assert "Kowalski" not in caplog.text
