"""Health surface (F-03).

``GET /health`` always returns HTTP 200 (FR-022) and reports per-dependency
status. Aggregation: overall ``degraded`` if any dependency is ``unavailable``,
otherwise ``ok`` (FR-024). Schema: contracts/health.openapi.yaml.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from .dependencies import get_redis_client

router = APIRouter()

REDIS_PING_TIMEOUT_S = 1.0  # FR-025


async def check_redis() -> str:
    """Return ``"ok"`` if Redis answers a ping within 1s, else ``"unavailable"``.

    Any exception (connection error, timeout, auth failure, missing URL) is
    classified as unavailable and never propagated as a 500 (FR-025, FR-028).
    """
    client = get_redis_client()
    if client is None:
        return "unavailable"
    try:
        await asyncio.wait_for(client.ping(), timeout=REDIS_PING_TIMEOUT_S)
        return "ok"
    except Exception:  # noqa: BLE001 — any failure means unavailable (FR-025)
        return "unavailable"


def check_spacy_model() -> str:
    """SpaCy model liveness.

    Epic 1 stub — always reports ``"ok"`` (FR-026, research D7).
    # TODO: wire real check in Epic 2 (NER engine: load/verify pl_core_news_lg).
    Epic 2 replaces only this function body; the endpoint, aggregation rule and
    response schema stay unchanged.
    """
    return "ok"


@router.get("/health")
async def get_health() -> dict:
    """Liveness + dependency status. ALWAYS HTTP 200 (FR-022)."""
    dependencies = {
        "redis": await check_redis(),
        "spacy_model": check_spacy_model(),
    }
    status = "ok" if all(v == "ok" for v in dependencies.values()) else "degraded"
    return {"status": status, "dependencies": dependencies}
