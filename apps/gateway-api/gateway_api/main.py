"""FastAPI application entry point (F-01/F-02/F-03 wiring).

Creates the app, mounts the health router, and installs the
``redis_availability_gate`` middleware that returns 503 on every non-health
route while Redis is unavailable (FR-027) — keeping ``/health`` always
reachable (FR-022).

Configuration is validated at import time (fail-fast), so an invalid
``REDIS_ENCRYPTION_KEY`` aborts startup before a port is bound (FR-019, SC-003).
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .health import check_redis
from .health import router as health_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway_api")

# Fail-fast: instantiating Settings here raises ValueError on an invalid
# encryption key before uvicorn binds a socket (FR-019, SC-003).
settings = get_settings()

# Log only operational metadata — never secrets (FR-030, Constitution VIII).
# Note we log whether Redis is configured, not the URL/password, and never the
# encryption key or any API key.
logger.info(
    "Configuration loaded: provider=%s model=%s redis_configured=%s session_ttl=%s",
    settings.default_llm_provider,
    settings.default_model,
    bool(settings.redis_url),
    settings.redis_session_ttl,
)

app = FastAPI(title="LLM Anonymization Gateway", version="0.1.0")
app.include_router(health_router)


@app.middleware("http")
async def redis_availability_gate(request: Request, call_next):
    """Pass ``/health`` through untouched; gate all other routes on Redis.

    Logs request path, status, and timing only — no headers, query, body, or
    secrets (FR-030).
    """
    start = time.perf_counter()
    path = request.url.path

    if path == "/health":
        response = await call_next(request)
    elif await check_redis() != "ok":
        response = JSONResponse(
            status_code=503, content={"detail": "Redis unavailable"}
        )
    else:
        response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request path=%s status=%s duration_ms=%.1f",
        path,
        response.status_code,
        duration_ms,
    )
    return response
