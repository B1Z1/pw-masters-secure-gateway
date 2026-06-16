"""Runtime dependency handles (research D4).

A process-singleton async Redis client. Construction is lazy and MUST NOT raise
on a missing or malformed ``REDIS_URL`` — only actual operations (ping/get/set)
fail. A Redis outage therefore never crashes the process (FR-028); liveness is
re-evaluated per request, giving automatic recovery when Redis returns.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from .config import get_settings

logger = logging.getLogger("gateway_api")

_client: Redis | None = None


def get_redis_client() -> Redis | None:
    """Return the lazily-constructed async Redis client, or ``None``.

    Returns ``None`` when ``REDIS_URL`` is absent or the URL cannot be parsed;
    callers treat that as an unavailable dependency rather than an error.
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    if not settings.redis_url:
        return None

    try:
        _client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:  # noqa: BLE001 — never raise on bad URL (FR-028, D4)
        logger.warning("Could not construct Redis client from REDIS_URL")
        return None

    return _client
