"""US3 observability hygiene (SC-002, FR-030).

Asserts that no secret value leaks into logs during startup or a request, and
that /health responds well within its latency budget with a mocked Redis.
"""

from __future__ import annotations

import logging
import os
import time
from unittest.mock import AsyncMock


def _mock_redis_ok() -> AsyncMock:
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    return client


# The concrete secret values established by conftest.
SECRETS = [
    os.environ["REDIS_PASSWORD"],
    os.environ["REDIS_ENCRYPTION_KEY"],
]


async def test_no_secrets_in_logs(client, monkeypatch, caplog):
    monkeypatch.setattr("gateway_api.health.get_redis_client", lambda: _mock_redis_ok())
    with caplog.at_level(logging.DEBUG):
        # Re-emit the startup config line and exercise a request.
        import gateway_api.main as main  # noqa: F401  (import triggers startup log)

        await client.get("/health")
        await client.get("/v1/anything")

    for secret in SECRETS:
        assert secret not in caplog.text


async def test_health_latency_under_budget(client, monkeypatch):
    monkeypatch.setattr("gateway_api.health.get_redis_client", lambda: _mock_redis_ok())
    start = time.perf_counter()
    resp = await client.get("/health")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < 500  # SC-002
