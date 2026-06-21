"""Epic 6 logging & metrics middleware (FR-013..FR-017).

A middleware DISTINCT from the Epic 1 Redis-availability gate, registered
OUTERMOST so it wraps every route and emits EXACTLY ONE structured JSON line per
request to stdout — including a gate 503 when Redis is down. It creates the
``RequestMetrics`` on ``request.state`` so the chat endpoint can fill the per-stage
timing + per-type counts; the middleware then reads and emits them.

Constitution VIII: the line carries metadata only — never original PII, message
content, or fake values. ``endpoint`` is the matched ROUTE TEMPLATE (e.g.
``/v1/sessions/{session_id}``), so no path-parameter value is ever logged; the
``session_id`` is a random hex (non-PII) logged as its own field. A logging failure
is caught and reported to stderr; the response is returned normally (FR-017).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .request_metrics import RequestMetrics


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        # Shared via the request scope's state, so the chat endpoint fills the
        # same object the emit below reads (D11).
        request.state.gateway_metrics = RequestMetrics()

        response = await call_next(request)

        try:
            _emit_log_line(request, start)
        except Exception as exc:  # noqa: BLE001 — logging never breaks a request
            print(f"request-logging failed: {exc}", file=sys.stderr)

        return response


def _route_template(request: Request) -> str:
    """The matched route path template (no path-param VALUES — FR-016)."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


def _emit_log_line(request: Request, start: float) -> None:
    metrics: RequestMetrics = getattr(
        request.state, "gateway_metrics", None
    ) or RequestMetrics()

    # Prefer the endpoint-measured total; fall back to the middleware wall-clock
    # (e.g. a gated 503 or any non-chat request).
    if metrics.total_ms <= 0.0:
        metrics.total_ms = (time.perf_counter() - start) * 1000

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": metrics.session_id,
        "endpoint": _route_template(request),
        "provider": metrics.provider,
        "model": metrics.model,
        "entities_detected": metrics.entities_detected if metrics.is_chat else None,
        "timing_ms": metrics.timing_ms(),
    }
    print(json.dumps(record), file=sys.stdout)
