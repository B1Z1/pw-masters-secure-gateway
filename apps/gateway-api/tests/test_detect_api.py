"""POST /v1/detect endpoint tests (T012, US1, FR-001/FR-002/FR-003/FR-006/FR-027)."""

from __future__ import annotations

from unittest.mock import Mock

from presidio_analyzer import RecognizerResult


async def test_detect_returns_entities(client, model_ready, patch_analyzer):
    text = "Jan 44051401359"
    r = RecognizerResult(entity_type="PESEL", start=4, end=15, score=0.99)
    r.recognition_metadata = {"pii": {"gender": "male", "checksum_valid": True}}
    patch_analyzer([r])

    resp = await client.post("/v1/detect", json={"text": text})
    assert resp.status_code == 200
    entity = resp.json()["entities"][0]
    assert entity["entity_type"] == "PESEL"
    assert text[entity["start"] : entity["end"]] == entity["text"] == "44051401359"
    assert entity["metadata"]["gender"] == "male"
    assert entity["score"] <= 0.99


async def test_empty_input_returns_empty_list(client, model_ready, patch_analyzer):
    patch_analyzer([])
    resp = await client.post("/v1/detect", json={"text": ""})
    assert resp.status_code == 200
    assert resp.json() == {"entities": []}


async def test_detect_makes_no_redis_io(
    client, model_ready, patch_analyzer, monkeypatch
):
    # /v1/detect is exempt from the Redis gate and detection is stateless, so the
    # Redis client must never be touched during a detect request (FR-006/FR-031).
    spy = Mock(return_value=None)
    monkeypatch.setattr("gateway_api.health.get_redis_client", spy)
    patch_analyzer([])

    resp = await client.post("/v1/detect", json={"text": "abc"})
    assert resp.status_code == 200
    assert spy.call_count == 0


async def test_malformed_body_returns_422(client, model_ready):
    resp = await client.post("/v1/detect", json={"not_text": 1})
    assert resp.status_code == 422
