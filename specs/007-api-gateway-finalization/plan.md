# Implementation Plan: EPIC 6 — API Gateway: Frontend-Ready Backend Surface, Logging/Metrics & Session Management

**Branch**: `im/06-finalize-api` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-api-gateway-finalization/spec.md`

## Summary

Harden the EPIC 4/5 HTTP surface into the complete, frontend-ready backend contract — **no new
anonymization, detection, generation, or routing logic**. The chat flow (pseudonymize the whole
history → call one provider via the EPIC 5 router → de-pseudonymize the answer) is unchanged; what
changes is the **response shape**, plus three new read/manage surfaces and one observability
middleware. Two agreed lower-layer extensions make the contract possible: the provider **port now
returns a finish reason** (`complete()` returns a small `CompletionResult{content, finish_reason,
provider}` instead of a bare `str`), and the **pipeline now returns per-stage timing + per-type entity
metrics**. Everything else (the `MappingStore`, the Redis `fwd:/rev:/forms:/meta/corefs` layout, the
AES-256-GCM envelope, the EPIC 5 adapters/router, the detection/generation layers) is **reused and
frozen**.

Delivered:
- **`POST /v1/chat/completions`** returns the full OpenAI-shaped body (`id`, `object`, `created`,
  `model`, `choices[0]` with a **real, normalized** `finish_reason`) plus `session_id`,
  `anonymization_meta` (per-type counts over the whole history, totals, provider, model,
  `processing_time_ms`, `timing_ms`), and `input_anonymization` (the latest user message's synthetic
  text + replacements with offsets into the original). Validation moves to a **permissive request
  model + manual checks** so every 400/429/503/504 preserves `session_id`. The centralized
  `kind → HTTP` map is reused unchanged.
- **`GET /v1/providers`** — read-only provider/key-presence discovery for the config panel
  (gate-exempt; never returns key values).
- **`GET` / `DELETE /v1/sessions/{session_id}`** — session statistics (for the dashboard) and reset,
  with the 404 matrix for non-existent / TTL-expired / never-stored sessions.
- **Logging & metrics middleware** — a separate, outermost middleware emitting exactly one structured
  JSON line per request (stage timing + per-type counts), provably free of PII/content/fakes, with a
  logging failure that never breaks the request.

Decisions are fixed in [research.md](./research.md) (D1–D14); component/transport/store shapes in
[data-model.md](./data-model.md) and [contracts/](./contracts/); validation flow in
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, `pydantic` / `pydantic-settings`, `redis.asyncio`; reused EPIC 5
`openai` / `anthropic` SDKs and the `httpx`-based Ollama adapter; Presidio + spaCy `pl_core_news_lg`,
Faker `pl_PL`, `cryptography` via the frozen EPIC 2/3/4 layers. **No new dependency** — the new
surface is plain FastAPI routers + one Starlette middleware over existing components.

**Storage**: Redis 7 — reused EPIC 3 session store; the `fwd:/rev:/forms:/meta/corefs` layout and the
AES-256-GCM envelope are **frozen**. This epic persists **no new fields**: it begins *incrementing* the
already-defined `SessionMeta.message_count` and reads `created_at`/`last_activity`/the live TTL that
already exist.

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), `fakeredis`; provider clients are
replaced by the reused `EchoProvider` / recording doubles (now returning `CompletionResult`). No real
keys, no network. Logs are asserted via `caplog`/captured stdout for the no-PII proof.

**Target Platform**: Linux server via Docker Compose (network `pw-masters-secure-gateway`); also native
via `uv` (`apps/gateway-api`, package `gateway_api`) in the Nx monorepo.

**Project Type**: Web service (backend `apps/gateway-api`); this epic makes it the complete backend for
the EPIC 7 React SPA.

**Performance Goals**: None defined (Constitution V — synchronous; latency is dominated by the upstream
provider). `timing_ms` is for *observability/dashboard*, not an SLA.

**Constraints**: No original PII in logs, content, fakes, or any outgoing provider request
(Constitution I/VIII); AES-256 mapping + session TTL unchanged (III); synchronous only — no streaming
(V); no auth on any endpoint (documented prototype limitation); the EPIC 2/3/4/5 regression contract
(public behaviour + Redis/encryption wire formats) is unchanged apart from the two agreed extensions.

**Scale/Scope**: Master's-thesis prototype; one chat endpoint hardened to full contract + three small
read/manage endpoints + one logging middleware; multi-turn Polish civil-law conversations;
trusted/dev exposure.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy by Design | PASS | The pipeline is unchanged: every message is pseudonymized before the single `provider.complete`. New surfaces are read/manage only; none send originals to a provider. `input_anonymization` returns originals to the **client only** — the trusted hop (FR-006); the provider still receives only synthetic data. |
| II. Recall over Precision | PASS | Detection reused unchanged; no thresholds touched. |
| III. Reversibility within Session | PASS | EPIC 3 store/encryption/TTL untouched; no new persisted fields; `message_count` (already in `SessionMeta`) is now incremented. `DELETE` removes the whole session hash (mappings included). |
| IV. Provider Agnosticism | PASS | The endpoint stays provider-agnostic: it reads `provider`/`finish_reason` from the port's `CompletionResult` (self-reported by each adapter) and never inspects prefixes. Routing stays in the router. `/v1/providers` lists providers from config, not from the chat path. |
| V. Synchronous Only | PASS | No streaming added; the full answer is received before de-pseudonymization; SSE remains out of scope. |
| VI. Polish First | PASS | No detection/generation changes; Polish handling is upstream and untouched. |
| VII. Realistic Substitution | PASS | Reuses EPIC 3 realistic fakes; no placeholders. |
| VIII. No PII in Logs | PASS | **Epic's CRITICAL gate.** The new log line carries only `timestamp`, `session_id` (random hex, non-PII), `endpoint` (route **template** — no path-param values), `provider`, `model`, per-type `entities_detected`, and `timing_ms` — never content/originals/fakes. `entities_detected`/`input_anonymization.replacements` appear in the **HTTP response to the trusted client**, never in logs. Proven via `caplog`/stdout audits (D13). |
| IX. Simplicity over Completeness | PASS | No new logic; reuses store/pipeline/router. The six `timing_ms` stages are measured at instrumented boundaries with a documented approximation (D4). The pre-existing debug `GET /v1/sessions/{id}/mappings` is kept as-is; the never-stored-session → 404 rule keeps PII-free sessions stateless (D7/D8). |

**Result**: PASS, no violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-api-gateway-finalization/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1–D14 (port ext, finish-reason, metrics, validation, sessions, providers, logging)
├── data-model.md        # Phase 1 — transport/response models, port + pipeline + store/repo deltas, config, Redis (frozen)
├── quickstart.md        # Phase 1 — offline + live validation guide
├── contracts/
│   ├── chat-completions.md   # full response + validation/error contract
│   ├── providers.md          # GET /v1/providers
│   ├── sessions.md           # GET/DELETE /v1/sessions/{id} + 404 matrix
│   └── logging-middleware.md # one structured JSON line; PII-free; failure-safe
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
apps/gateway-api/gateway_api/
├── api/
│   ├── chat.py                     # CHANGED — full response contract (id/object/created/model/choices+real finish_reason,
│   │                               #   anonymization_meta, input_anonymization); permissive request model + manual
│   │                               #   validation (every 400 preserves session_id); request.state metrics; message_count bump
│   ├── sessions.py                 # NEW — GET/DELETE /v1/sessions/{session_id} (summary + reset; 404 matrix)
│   ├── providers.py                # NEW — GET /v1/providers (name/requires_key/key_configured; no key values)
│   ├── pseudonymize.py             # UNCHANGED — keeps the debug GET /v1/sessions/{id}/mappings (coexists)
│   └── detect.py                   # UNCHANGED
├── llm_providers/
│   ├── base.py                     # CHANGED — add CompletionResult{content,finish_reason,provider} + normalize_finish_reason;
│   │                               #   complete() now returns CompletionResult (port extension, FR-022). kind enum unchanged.
│   ├── openai_provider.py          # CHANGED — return CompletionResult (raw finish_reason normalized; provider="openai")
│   ├── anthropic_provider.py       # CHANGED — return CompletionResult (stop_reason normalized; provider="anthropic")
│   ├── ollama_provider.py          # CHANGED — return CompletionResult (done_reason normalized; provider="ollama")
│   ├── echo_provider.py            # CHANGED — return CompletionResult(finish_reason="stop", provider="echo")
│   ├── llm_router.py               # CHANGED — complete() return annotation → CompletionResult (pure pass-through)
│   └── __init__.py                 # UNCHANGED — get_llm_provider() still returns the router
├── observability/                  # NEW package
│   ├── __init__.py
│   ├── request_metrics.py          # NEW — RequestMetrics (stage timers) + contextvar inbound redis-write sink
│   └── request_logging.py          # NEW — the logging/metrics middleware (outermost; one JSON line; failure-safe)
├── pipeline/
│   └── anonymization_pipeline.py   # CHANGED — run_inbound() → InboundResult{fake_messages, entities_detected,
│                                   #   last_user_pseudonymized, last_user_replacements, timing}; pseudonymize_text reused
├── pseudonym_vault/
│   ├── session_mapping_repository.py # CHANGED — read_meta(), ttl_seconds(), delete()→existed:bool,
│   │                                 #   bump_message_count() (no-op when no meta); inbound redis-write timing hook
│   └── mapping_store.py              # CHANGED — get_session_summary(), increment_message_count(), delete_session()→bool
└── main.py                         # CHANGED — include sessions+providers routers; register logging middleware OUTERMOST;
                                    #   add "/v1/providers" to gate-exempt; drop the gate's plain per-request log line

apps/gateway-api/tests/
├── test_chat_api.py                # CHANGED — full contract fields; finish_reason normalization; entities_detected over
│                                   #   history; input_anonymization offsets; validation matrix preserves session_id;
│                                   #   no-PII-in-logs; doubles now return CompletionResult
├── test_sessions_api.py            # NEW — GET/DELETE 200/404 matrix; entity_count/entities_by_type; message_count; ttl
├── test_providers_api.py           # NEW — requires_key/key_configured; no secret leak; works while Redis down
├── test_request_logging.py         # NEW — exactly one JSON line; required fields; no PII/content/fakes; failure-safe; route template
├── test_pipeline_inbound.py        # NEW — run_inbound: entities_detected over history; last-message replacements; timing present
└── llm_providers/
    ├── test_openai_provider.py     # CHANGED — finish_reason normalization (length/stop), provider name, CompletionResult
    ├── test_anthropic_provider.py  # CHANGED — stop_reason→finish_reason normalization, provider name
    ├── test_ollama_provider.py     # CHANGED — done_reason→finish_reason normalization (+missing→stop), provider name
    └── test_llm_router.py          # CHANGED — CompletionResult pass-through unchanged dispatch

apps/gateway-api/pyproject.toml     # UNCHANGED — no new dependency
docs/postman + dev docs             # NOTE — add the three new endpoints + richer chat-response examples (D14)
```

**Structure Decision**: Single backend service `apps/gateway-api` (package `gateway_api`). New HTTP
surfaces are thin FastAPI routers (`api/sessions.py`, `api/providers.py`) plus a new `observability/`
package for the metrics object and the logging middleware; the chat handler, the provider port, the
pipeline, and the store/repository receive the additive changes above. No frontend code in this epic
(EPIC 7).

## Complexity Tracking

> No Constitution violations — section intentionally empty.
