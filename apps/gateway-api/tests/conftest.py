"""Shared pytest fixtures for the gateway-api test suite.

A valid configuration environment is established at import time (before the app
module is imported) so that fail-fast settings validation does not abort
collection. Individual tests patch ``gateway_api.health.get_redis_client`` to
drive Redis behavior.
"""

from __future__ import annotations

import base64
import os

# Valid 32-byte (base64) AES key + required Redis settings, set before the app
# module is imported anywhere.
os.environ.setdefault("REDIS_PASSWORD", "testpass")
os.environ.setdefault(
    "REDIS_ENCRYPTION_KEY", base64.b64encode(b"0" * 32).decode()
)
os.environ.setdefault("REDIS_URL", "redis://:testpass@localhost:6379/0")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """An httpx.AsyncClient bound to the ASGI app (no network)."""
    from gateway_api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
