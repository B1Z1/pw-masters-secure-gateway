"""Detect gating tests (T043, US5, FR-030/FR-031)."""

from __future__ import annotations


async def test_detect_503_when_model_not_ready(client, model_not_ready):
    resp = await client.post("/v1/detect", json={"text": "abc"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Detection model not ready"


async def test_detect_served_when_redis_down(
    client, model_ready, patch_analyzer, monkeypatch
):
    # Redis unavailable, but /v1/detect is exempt from the gate (FR-031).
    monkeypatch.setattr("gateway_api.health.get_redis_client", lambda: None)
    patch_analyzer([])
    resp = await client.post("/v1/detect", json={"text": "abc"})
    assert resp.status_code == 200


async def test_other_route_still_gated_when_redis_down(client, monkeypatch):
    monkeypatch.setattr("gateway_api.health.get_redis_client", lambda: None)
    resp = await client.get("/v1/anything")
    assert resp.status_code == 503
