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
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.chat import router as chat_router
from .api.detect import router as detect_router
from .api.providers import router as providers_router
from .api.pseudonymize import router as pseudonymize_router
from .api.sessions import router as sessions_router
from .config import get_settings
from .health import check_redis
from .health import router as health_router
from .observability.request_logging import RequestLoggingMiddleware
from .pii_detection import nlp as detection_nlp

# Routes exempt from the Redis-availability gate. /health (FR-022), the stateless
# detection endpoint (/v1/detect — FR-031), and the read-only provider discovery
# (/v1/providers — Epic 6 FR-011, needs no Redis) never depend on Redis.
_GATE_EXEMPT_PATHS = frozenset({"/health", "/v1/detect", "/v1/providers"})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway_api")

# Fail-fast: instantiating Settings here raises ValueError on an invalid
# encryption key before uvicorn binds a socket (FR-019, SC-003).
settings = get_settings()

# Log only operational metadata — never secrets (FR-030, Constitution VIII).
# Note we log whether Redis is configured, not the URL/password, and never the
# encryption key or any API key.
logger.info(
    "Configuration loaded: model=%s redis_configured=%s session_ttl=%s",
    settings.default_model,
    bool(settings.redis_url),
    settings.redis_session_ttl,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly load the spaCy model in the background at startup (research D8).

    Runs in a worker thread so /health stays reachable and the event loop is not
    blocked during the multi-second load. ``ensure_loaded`` never raises; on
    failure the model stays unavailable (health degraded, /v1/detect 503).
    """
    threading.Thread(
        target=detection_nlp.ensure_loaded, name="spacy-model-load", daemon=True
    ).start()
    yield


app = FastAPI(title="LLM Anonymization Gateway", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(detect_router)
# Epic 3 substitution routes — NOT gate-exempt: they require Redis, so the Epic 1
# middleware 503s them when Redis is down (unlike the stateless /v1/detect).
app.include_router(pseudonymize_router)
# Epic 4 chat round-trip — also NOT gate-exempt (it needs Redis via the store).
app.include_router(chat_router)
# Epic 6 — session management (GET/DELETE, need Redis) + provider discovery
# (gate-exempt above).
app.include_router(sessions_router)
app.include_router(providers_router)


@app.middleware("http")
async def redis_availability_gate(request: Request, call_next):
    """Pass gate-exempt routes through; gate all others on Redis availability.

    The per-request structured log line is emitted by the separate
    ``RequestLoggingMiddleware`` (Epic 6) — this gate no longer logs, so there is
    exactly one structured line per request and the two do not duplicate (FR-013).
    """
    if request.url.path in _GATE_EXEMPT_PATHS:
        return await call_next(request)

    if await check_redis() != "ok":
        return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})

    return await call_next(request)


# Registered AFTER the gate so it is the OUTERMOST middleware: it wraps the gate
# and therefore logs EVERY response — including a gate 503 — exactly once (D10).
app.add_middleware(RequestLoggingMiddleware)
