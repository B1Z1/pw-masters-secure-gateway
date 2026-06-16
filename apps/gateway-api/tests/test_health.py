"""The five required Epic-1 backend cases (quickstart Scenario F)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from gateway_api.config import Settings


def _mock_redis(ping_result=None, ping_error=None) -> AsyncMock:
    client = AsyncMock()
    if ping_error is not None:
        client.ping = AsyncMock(side_effect=ping_error)
    else:
        result = ping_result if ping_result is not None else True
        client.ping = AsyncMock(return_value=result)
    return client


# 1. /health -> 200 + "ok" when Redis ping succeeds.
async def test_health_ok_when_redis_up(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_api.health.get_redis_client", lambda: _mock_redis(ping_result=True)
    )
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {"redis": "ok", "spacy_model": "ok"}


# 2. /health -> 200 + "degraded" when Redis ping raises ConnectionError.
async def test_health_degraded_when_redis_down(client, monkeypatch):
    monkeypatch.setattr(
        "gateway_api.health.get_redis_client",
        lambda: _mock_redis(ping_error=RedisConnectionError("down")),
    )
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["redis"] == "unavailable"
    assert body["dependencies"]["spacy_model"] == "ok"


# 3. Any non-health route -> 503 when Redis is unavailable.
async def test_non_health_route_503_when_redis_unavailable(client, monkeypatch):
    monkeypatch.setattr("gateway_api.health.get_redis_client", lambda: None)
    resp = await client.get("/v1/anything")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Redis unavailable"}


# 4. Settings() with an invalid REDIS_ENCRYPTION_KEY raises (ValueError).
def test_invalid_encryption_key_raises():
    with pytest.raises(ValueError):
        Settings(redis_password="x", redis_encryption_key="not-base64!!")


# 5. Settings() with an empty OPENAI_API_KEY does NOT raise.
def test_empty_openai_key_does_not_raise():
    valid_key = base64.b64encode(b"0" * 32).decode()
    settings = Settings(
        redis_password="x",
        redis_encryption_key=valid_key,
        openai_api_key="",
    )
    assert settings.openai_api_key == ""
