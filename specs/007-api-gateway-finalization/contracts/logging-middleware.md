# Contract: Logging & Metrics Middleware (one structured, PII-free JSON line per request)

**Feature**: EPIC 6 | `gateway_api/observability/request_logging.py` (+ `request_metrics.py`) +
`main.py` wiring. A FastAPI/Starlette middleware **distinct** from the EPIC 1 Redis-availability gate,
registered **outermost** so it wraps every route (D10). The chat endpoint/pipeline stash metrics in
request-scoped state; the middleware reads and emits them (FR-013..FR-017).

## Placement & ordering

- Registered **after** the `redis_availability_gate` decorator → **outermost** layer (runs first
  inbound, last outbound). It therefore logs **every** response, including a gate **503** when Redis is
  down (those carry no chat metrics — `total` only).
- The Redis gate **keeps** its gating job but its plain `logger.info("request path=…")` line is
  **removed** → exactly **one** per-request log line; the two middlewares do not duplicate (FR-013).

## Emitted line (stdout, JSON)

```jsonc
{
  "timestamp": "2026-06-18T10:05:00.123+00:00",
  "session_id": "…" ,                 // or null (non-chat / pre-session)
  "endpoint": "/v1/sessions/{session_id}",  // matched ROUTE TEMPLATE — never raw path-param values
  "provider": "ollama",               // or null (non-chat)
  "model": "ollama/qwen2.5:3b",       // or null (non-chat)
  "entities_detected": { "PERSON": 2, "PESEL": 1 },  // or {} / null (non-chat)
  "timing_ms": {                      // six stages for chat; for non-chat only `total` is meaningful
    "ner_analysis": 12.0, "fake_generation": 8.0, "redis_write": 5.0,
    "llm_request": 1200.0, "deanonymization": 9.5, "total": 1234.5
  }
}
```

For chat requests, `timing_ms` is the **same object** also returned in
`anonymization_meta.timing_ms` (FR-005 / D11).

## Invariants (Constitution VIII — CRITICAL)

- **Never** contains original PII, message content, or fake values — only metadata. `entities_detected`
  is per-type **counts**, never values.
- `endpoint` is the **matched route template** (e.g. `/v1/sessions/{session_id}`), so no path-parameter
  value is logged — the path-PII sanitization required by FR-016 (the architecture puts no PII in URLs;
  `session_id`, a random hex, is non-PII and is logged as its own field).
- **Failure-safe** (FR-017): the entire emit is wrapped in `try/except`; any error is caught, written to
  **stderr**, and the response is returned normally — logging never breaks a request.
- **Exactly one** line per request (FR-013).

## Request-scoped state (D11)

The middleware creates a `RequestMetrics` and exposes it on `request.state` before `call_next`. The chat
endpoint records `llm_request` + `deanonymization`, folds in the pipeline's inbound stages
(`ner_analysis`, `fake_generation`, `redis_write`) and `entities_detected`, and sets
`session_id`/`provider`/`model`. After `call_next` the middleware reads `request.state`, finalizes
`total`, and emits. Non-chat requests leave chat fields unset → `null`/`{}` with a meaningful `total`.

## Acceptance assertions (map to spec)

- Exactly one JSON line per request with all required fields + the six timing stages (SC-007; FR-013/FR-014).
- Audit proves no original / content / fake value in the line (SC-007/SC-009; FR-016).
- Forced emit failure → chat response still 200, error to stderr (SC-007; FR-017).
- `endpoint` is the route template (no path-param value) (FR-016).
