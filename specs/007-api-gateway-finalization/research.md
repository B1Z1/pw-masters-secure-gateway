# Research: EPIC 6 — API Gateway Finalization (frontend-ready surface, logging/metrics, sessions)

**Feature**: `specs/007-api-gateway-finalization` | **Date**: 2026-06-18

This document resolves the design unknowns for EPIC 6. The stack is fixed (Constitution Technology
Constraints + the EPIC 4/5 plans); no alternatives to Python 3.12 / FastAPI / `redis.asyncio` are
evaluated. Each decision records what was chosen, why, and the alternative rejected. The chat **flow**
(pseudonymize whole history → one provider via the router → de-pseudonymize) is reused unchanged; the
only lower-layer changes are the **provider-port finish reason** (D1/D2) and the **pipeline
timing/entity metrics** (D3/D4) — both named in the spec as in-scope. The detection/generation layers,
the `MappingStore`, the Redis layout, the AES-256-GCM envelope, and the EPIC 5 adapters/router are
**frozen**.

---

## D1 — Provider port extension: `complete()` returns `CompletionResult`, not `str`

**Decision**: Change the port's contract from `async complete(...) -> str` to
`async complete(...) -> CompletionResult`, a small immutable value object in `base.py`:

```text
@dataclass(frozen=True)
class CompletionResult:
    content: str          # the assistant text (de-pseudonymized downstream)
    finish_reason: str    # already normalized to OpenAI vocab ("stop" | "length") — see D2
    provider: str         # the concrete provider name ("openai" | "anthropic" | "ollama" | "echo")
```

Every adapter returns it; the **router passes it through** unchanged (it only annotates the return
type). The endpoint reads `result.content`, `result.finish_reason`, and `result.provider` and stays
**provider-agnostic** — it never inspects model prefixes to learn the provider (Constitution IV). This
is the FR-022 agreed port extension.

**Rationale**: EPIC 4 hardcoded `finish_reason: null` because the port returned only text; the frontend
now needs the **real** finish reason (FR-003) and the **concrete provider** that served the request
(FR-005). Carrying both in the return value (rather than a side channel or a second method) keeps the
single `complete()` call site and lets each adapter self-report what only it knows — its own name and
its own raw finish reason — without leaking provider knowledge into the endpoint.

**Alternatives rejected**:
- *Keep `-> str`, derive provider from the model prefix in the endpoint* — couples the endpoint to
  routing rules (violates Constitution IV / the EPIC 5 boundary).
- *Add `finish_reason()`/`last_provider()` as separate port methods* — stateful, race-prone under a
  shared singleton; two calls where one suffices.
- *Return a `dict`/`tuple`* — loses the named, typed contract `CompletionResult` gives every adapter
  and test.

---

## D2 — Finish-reason normalization: one mapping in `base.py`, fed each provider's raw value

**Decision**: A single pure function `normalize_finish_reason(raw: str | None) -> str` in `base.py`
maps every provider's raw value to the OpenAI vocabulary the contract guarantees, defaulting to
`"stop"`:

| Raw value (source) | Normalized |
|--------------------|-----------|
| `stop` (OpenAI/Ollama) | `stop` |
| `length` (OpenAI/Ollama) | `length` |
| `end_turn`, `stop_sequence` (Anthropic) | `stop` |
| `max_tokens` (Anthropic) | `length` |
| anything else, `None`, missing (echo/stub) | `stop` |

Each adapter passes its own raw field: OpenAI `response.choices[0].finish_reason`; Anthropic
`response.stop_reason`; Ollama `response.json().get("done_reason")` (absent on older Ollama → `None` →
`"stop"`); `EchoProvider` passes `None`. The function is the **single source** of the OpenAI vocabulary
so the table is not duplicated per adapter.

**Rationale**: FR-003 requires a real value normalized to `stop`/`length`, with a `stop` fallback for
providers that cannot report one. Centralizing the (small, total) mapping keeps adapters trivial and
the vocabulary single-sourced; it also preserves EPIC 5's existing length-truncation behaviour (OpenAI
still logs the warning and returns partial content — D-note below).

**Note (reuse)**: EPIC 5's OpenAI length-truncation warning + partial-content return is **kept**; this
epic only additionally *surfaces* the normalized `length` to the client. No adapter raises on
truncation.

**Alternatives rejected**: *Per-adapter inline mapping* — duplicates the vocabulary in three places;
*pass raw provider values straight through* — violates "normalized to OpenAI vocabulary" (FR-003).

---

## D3 — Pipeline inbound result: `run_inbound()` → `InboundResult` (replaces `pseudonymize_messages`)

**Decision**: Replace `AnonymizationPipeline.pseudonymize_messages(...)` (its only caller is the chat
endpoint) with `run_inbound(session_id, messages) -> InboundResult`:

```text
@dataclass
class InboundResult:
    fake_messages: list[ChatMessage]          # whole history, every message pseudonymized
    entities_detected: dict[str, int]         # per-type counts over the WHOLE history (FR-005)
    total_entities: int                       # sum
    last_user_pseudonymized: str              # synthetic latest user message (FR-006)
    last_user_replacements: list[Replacement] # offsets into the ORIGINAL latest user message (FR-006)
    timing: InboundTiming                      # ner_analysis_ms, fake_generation_ms, redis_write_ms (D4)
```

It reuses `pseudonymize_text(session_id, text) -> (fake_text, replacements)` per message (unchanged,
still used by the debug `/v1/pseudonymize`), collecting: the fake messages, the **per-type counts
summed across all messages** (per detected occurrence per message — the spec's natural reading), and —
for the **last** message specifically — its synthetic content and its replacement list. The endpoint
then calls `provider.complete(result.fake_messages, model=…)` exactly as before.

**Rationale**: One inbound pass already produces every datum the response needs (FR-005/FR-006);
returning them from a single richer method avoids a second detection pass or a debug-endpoint
round-trip (the spec forbids the latter). `entities_detected` is over the whole history (what the
dashboard shows); `input_anonymization` is the last user message only (what the per-message UI shows) —
both fall out of the same loop. Keeping `pseudonymize_text` intact preserves the EPIC 3 debug contract.

**Alternatives rejected**: *Keep `pseudonymize_messages` and add a parallel method* — two inbound passes
or duplicated loops; *compute `input_anonymization` by re-detecting the last message in the endpoint* —
a second detection pass and detection logic leaking into the handler.

---

## D4 — Per-stage `timing_ms`: a request-scoped `RequestMetrics` with an inbound-only redis-write sink

**Decision**: Introduce `gateway_api/observability/request_metrics.py` with a `RequestMetrics` object
holding the six stage accumulators and a small `time_stage(name)` context manager. Stages are measured
at these boundaries:

| Stage | Measured around | Owner |
|-------|-----------------|-------|
| `ner_analysis` | each `engine.detect(text)` call (summed over messages) | pipeline `run_inbound` |
| `fake_generation` | the inbound substitution compute = (store time during inbound) − `redis_write` | pipeline (derived) |
| `redis_write` | the inbound Redis **write** ops (`hset`/`expire`) only | repository, via an inbound-scoped sink |
| `llm_request` | `await provider.complete(...)` | chat endpoint |
| `deanonymization` | `await pipeline.depseudonymize_text(...)` (its reads + restore, as one stage) | chat endpoint |
| `total` | end-to-end gateway wall-clock for the request | chat endpoint (== `processing_time_ms`) |

To split `fake_generation` from `redis_write` **without changing public signatures**, the repository's
write methods add their Redis-call duration to a `contextvars.ContextVar` "inbound redis-write sink"
that the pipeline sets **only around the inbound persistence** (so outbound `extend_ttl` writes during
de-pseudonymization are **not** counted into `redis_write` — they fall under `deanonymization`). When no
sink is active (the debug endpoints, tests not measuring), the hook is a zero-cost no-op.

**Stage semantics (documented, Constitution IX)**: `fake_generation` is the inbound store compute
*minus* the inbound Redis-write time (a small amount of inbound Redis **read** time is folded into it —
negligible and explicitly accepted). `deanonymization` is measured as the wall-clock of
`depseudonymize_text` (reads + compute + its own TTL refresh) as a single stage. `total` is the
endpoint's measured wall-clock and is the value reported as both `timing_ms.total` and
`anonymization_meta.processing_time_ms`. All stage values are non-negative milliseconds.

**Rationale**: FR-014/FR-015 require the six named stages. The contextvar sink is the **least-invasive**
way to separate the I/O stage (`redis_write`) from the CPU stage (`fake_generation`) — it threads no
parameters through `get_or_create → _substitute → _write_mapping → repository.write_mapping` and leaves
every public method signature unchanged, so the store stays "reused, not reimplemented".

**Alternatives rejected**:
- *Thread a `metrics` parameter through every store/repository method* — large signature churn across
  the frozen store for a metrics concern.
- *Wrap the shared Redis client in a timing proxy* — the store is a process singleton with one client;
  per-request swapping is fragile.
- *Collapse `fake_generation` + `redis_write` into one stage* — violates the explicit six-stage
  requirement (FR-014).

---

## D5 — Full chat response contract (transport models in `api/chat.py`)

**Decision**: Replace EPIC 4's minimal `ChatCompletionResponse{session_id, choices}` with the full
contract (models in `api/chat.py`; field shapes in [data-model.md](./data-model.md) §1 and the
[chat-completions contract](./contracts/chat-completions.md)):

- `id` = `"chatcmpl-" + uuid4().hex`; `object` = `"chat.completion"`; `created` = `int(time.time())`
  (unix seconds); `model` = the **resolved** model the endpoint computed (`request.model or
  settings.default_model`) — reported **un-stripped** (e.g. `ollama/qwen2.5:3b`), since that is the
  model "actually used" from the caller's point of view (the router strips `ollama/` internally only).
- `choices[0]` = `{index:0, message:{role:"assistant", content}, finish_reason}` where `finish_reason`
  is `CompletionResult.finish_reason` (D2) — now always a string.
- `anonymization_meta` = `{entities_detected, total_entities, provider, model, processing_time_ms,
  timing_ms}`; `provider` = `CompletionResult.provider`; `timing_ms` = the **same** object stashed for
  the log (FR-005).
- `input_anonymization` = `{pseudonymized_content, replacements}` from `InboundResult` (the pipeline's
  `Replacement` is reused as the item model; offsets index the original latest user message).

**Rationale**: This is the headline contract (FR-002..FR-006). Reusing the pipeline's `Replacement`
model for `input_anonymization.replacements` avoids a parallel type. `created`/`id`/`object` are static
shapes; `model`/`provider` come from data already in hand.

**Alternatives rejected**: *Stream usage/token accounting* — explicitly out of scope; *return the
stripped Ollama model name* — would misreport the "model used" the client asked for.

---

## D6 — Validation: permissive request model + manual checks so every 400 preserves `session_id`

**Decision**: The chat request model becomes permissive so FastAPI/pydantic does **not** 422 before the
handler runs (a 422 could not carry `session_id`). `messages` is a list of a permissive
`ChatInputMessage{role: str | None = None, content: Any = None}`; `session_id: str | None`,
`model: str | None`. The handler computes `session_id` first, then validates **in order**, returning
`_error(400, …, session_id)` on the first failure (no provider contacted):

1. `messages` non-empty;
2. every message: `role in {"system","user","assistant"}` **and** `content` is a non-`None` `str`;
3. the **last** message's role is `"user"`;
4. (after pseudonymize) the router's `unknown_model` → 400 via the existing `_ERROR_STATUS` map, also
   preserving `session_id` and listing the recognized prefixes.

Valid messages are converted to `ChatMessage` before the pipeline runs. The EPIC 5 error mapping
(`_ERROR_STATUS`: unreachable/missing_model/auth → 503, timeout → 504, rate_limit → 429, unknown_model →
400) and the `_error` helper are **reused unchanged**; inbound mappings already written on a failing
turn are **not** rolled back (FR-010).

**Rationale**: FR-007/FR-010 require all validation **before** any provider call and **every** error
body to preserve `session_id`. Pydantic's strict typing would reject bad `role`/`content` with a 422
that omits `session_id`; a permissive model + explicit checks puts the gateway in control of the status
and body.

**Alternatives rejected**: *Keep strict `ChatMessage` and add a `RequestValidationError` handler that
digs `session_id` out of the raw body* — brittle and indirect; *validate via pydantic validators* —
still raises 422 pre-handler without `session_id`.

---

## D7 — `message_count`: bump on success, only when the session already has stored state

**Decision**: `SessionMeta.message_count` (already defined, currently never incremented) is incremented
**by 1 per successful** `POST /v1/chat/completions`, via a new `MappingStore.increment_message_count`
→ `repository.bump_message_count(session_id)` that **reads `meta` and, if absent, does nothing**
(it never *creates* a session hash). The endpoint calls it after a successful round-trip (after
de-pseudonymization, before building the response).

This reconciles two spec rules: "+1 per successful round-trip" **and** "a session with no PII ever
detected has no stored state → 404". A turn that detected PII has already written `meta` during inbound
persistence, so the bump lands; a turn that detected **no** PII has no hash, so the bump is a no-op and
the session stays stateless (404 on GET/DELETE) — the accepted limitation. A failed turn (provider
error) does **not** bump (only success does), even though its inbound mappings persist (FR-010).

**Rationale**: Implements FR-019 without contradicting FR-021's never-stored-session 404. Tying
`message_count` to the existing `meta` hash means PII-free sessions remain "nothing to manage".

**Alternatives rejected**: *Always create state to count messages* — would make PII-free sessions
manageable, contradicting the 404 edge case; *count messages in a separate key* — a new persisted field
outside the frozen layout for no benefit.

---

## D8 — Session endpoints (`GET`/`DELETE /v1/sessions/{id}`) + the 404 matrix

**Decision**: New router `api/sessions.py` (Redis-dependent → **not** gate-exempt). New store/repository
methods:

- `repository.read_meta(session_id) -> dict | None` (decrypts the `meta` field, or `None`).
- `repository.ttl_seconds(session_id) -> int` (`await redis.ttl(key)`; Redis returns `-2` missing /
  `-1` no-expire).
- `repository.delete(session_id) -> bool` (return `await redis.delete(key) == 1` — *existed*).
- `store.get_session_summary(session_id) -> dict | None` orchestrating: `read_meta` (→ `None` ⇒ 404),
  `get_all_mappings` (existing — distinct pairs) grouped by `entity_type` into `entities_by_type` with
  `entity_count` = its sum, and `ttl_seconds`.
- `store.delete_session(session_id) -> bool` (delegates to `repository.delete`; also discards the
  in-process session lock).

`GET` returns `{session_id, created_at, last_activity, ttl_remaining_seconds, entity_count,
entities_by_type, message_count}` (created_at/last_activity/message_count from `meta`;
entity_count/entities_by_type from the distinct mappings; ttl from Redis). It returns **404** when
`get_session_summary` is `None` (no meta / TTL-expired-and-evicted / never stored). `DELETE` returns
success only when `delete_session` reports the key existed, else **404**. Both 404s use a plain JSON
`{"detail": …}` (no `session_id` echo needed — these are not the retryable chat path).

`entity_count`/`entities_by_type` come from `get_all_mappings` (**distinct** original↔fake pairs), **not**
from `meta.entity_count` (which is a write counter that can exceed the distinct count via coref reuse).
The pre-existing debug `GET /v1/sessions/{id}/mappings` (EPIC 3) is **kept** and coexists — FastAPI
distinguishes `/v1/sessions/{id}` from `/v1/sessions/{id}/mappings`.

**Rationale**: FR-018..FR-021. Distinct-pair grouping is exactly the dashboard bar chart; deriving it
from `get_all_mappings` reuses the reconstruction that already powers the debug listing. Using Redis
TTL/`delete` return values gives the live TTL and the existed/absent signal with no new persisted state.

**Alternatives rejected**: *Use `meta.entity_count` for the dashboard* — counts writes, not distinct
mappings (wrong bar chart); *check existence with a separate `exists` then `delete`* — two round-trips
where `delete`'s return value already tells us.

---

## D9 — Provider discovery (`GET /v1/providers`) — config-only, key-safe, gate-exempt

**Decision**: New router `api/providers.py` returning a fixed three-entry list built from `Settings`:

| name | requires_key | key_configured |
|------|--------------|----------------|
| `openai` | `true` | `bool(settings.openai_api_key)` |
| `anthropic` | `true` | `bool(settings.anthropic_api_key)` |
| `ollama` | `false` | `false` (no key concept) |

It returns **only** `{name, requires_key, key_configured}` — never a key value or any other secret
(FR-012). The route is added to `main._GATE_EXEMPT_PATHS` (it needs no Redis), so the config panel can
populate even while Redis is down — consistent with `/health` and the stateless `/v1/detect` already
being exempt.

**Rationale**: FR-011/FR-012 + the spec's "warn before the first message" goal. `key_configured` is a
boolean derived from presence; no value crosses the boundary. Gate-exemption lets the panel render in a
degraded stack.

**Alternatives rejected**: *Enumerate model names per provider* — EPIC 5 routes by prefix with **no**
model registry (the spec keeps it that way); the panel offers provider/prefix + free-text model.
*Accept keys from the client to test them* — forbidden (keys are `.env`-only, FR-012).

---

## D10 — Logging & metrics middleware: separate, outermost, one JSON line, failure-safe

**Decision**: New `gateway_api/observability/request_logging.py` middleware, registered in `main.py`
**after** the Redis-availability gate so it is the **outermost** layer (runs first inbound, last
outbound) and therefore logs **every** response — including a gate 503 when Redis is down. It:

1. records a start time and creates the `RequestMetrics`, exposing it on `request.state` so the chat
   endpoint can populate stage timings / `session_id` / `provider` / `model` / `entities_detected`;
2. calls the handler;
3. after the response, emits **exactly one** JSON line to **stdout** with: `timestamp` (ISO-8601 UTC),
   `session_id` (or `null`), `endpoint` (the **matched route template**, e.g.
   `/v1/sessions/{session_id}` — never the raw path, so no path-param value is ever logged),
   `provider`, `model`, `entities_detected` (per-type dict or `{}`), and `timing_ms` (the six stages;
   for non-chat requests only `total` — the middleware's own wall-clock — is meaningful, others `null`).

The existing Redis-gate middleware **keeps its gating job** but its plain
`logger.info("request path=… status=… duration_ms=…")` line is **removed**, so there is exactly **one**
per-request log line and the two middlewares do not duplicate each other (FR-013). The whole emit is
wrapped in `try/except`: any failure is caught, written to **stderr**, and the response is returned
normally (FR-017).

**Rationale**: FR-013/FR-014/FR-016/FR-017. Outermost placement guarantees one line per request for
*all* paths and a true end-to-end `total`. The matched route template is the PII-sanitization for paths
(FR-016) — `session_id` is a random hex (non-PII) and is logged as its own field; no message content,
originals, or fakes are ever in scope for the line. `try/except` around emit makes logging
non-load-bearing.

**Alternatives rejected**: *Log inside the chat handler* — misses non-chat requests and gate 503s, and
risks coupling logging to the happy path; *keep the gate's plain log too* — two lines per request
(violates "exactly one"); *log `request.url.path` raw* — would log `session_id` path values (acceptable
as non-PII, but the route template is strictly safer and future-proofs against any future PII-in-path).

---

## D11 — Request-scoped plumbing: `request.state` carries the metrics; one timing object, two readers

**Decision**: The chat endpoint takes the Starlette `Request` (added parameter) and reads the
`RequestMetrics` the middleware put on `request.state`. It records `llm_request` and `deanonymization`
there, folds in the pipeline's inbound `timing` and `entities_detected`, sets `session_id`, `provider`,
`model`, and finalizes `total`. It then builds **one** `timing_ms` dict that is placed **both** into
`anonymization_meta.timing_ms` (the HTTP response, FR-005) and read by the middleware from
`request.state` for the log line — guaranteeing they are the *same* object. `processing_time_ms` ==
`timing_ms["total"]`.

**Rationale**: FR-005 says the response `timing_ms` is "the same per-stage timing object emitted to the
logs". `request.state` is the idiomatic Starlette request-scoped channel and is shared between handler
and surrounding middleware, so the handler-populated metrics are visible to the middleware after
`call_next` (the spec literally says "stash these metrics in request-scoped state; the middleware reads
and emits them").

**Alternatives rejected**: *A module-global/contextvar for the whole metrics object* — `request.state`
is the correct scope and avoids leakage across concurrent requests; *recompute timing in the
middleware* — could not reproduce the per-stage breakdown the handler measured.

---

## D12 — Wiring & registration (`main.py`)

**Decision**: `main.py` (1) `include_router(sessions_router)` and `include_router(providers_router)`;
(2) registers the logging/metrics middleware so it is **outermost** (added after the
`redis_availability_gate` decorator); (3) adds `"/v1/providers"` to `_GATE_EXEMPT_PATHS`; (4) removes
the gate's plain per-request log line (D10). `get_llm_provider()` and the router wiring are
**unchanged** (the chat endpoint still depends only on the port). The startup config log is unchanged.

**Rationale**: Minimal, declarative wiring; keeps the EPIC 1 gate's responsibility intact while making
the new logger authoritative for per-request lines.

**Alternatives rejected**: *Gate-exempt the session endpoints too* — they need Redis, so a 503 when
Redis is down is correct (the dashboard has nothing to read anyway).

---

## D13 — Testing strategy (network-free; no keys; PII-leak audited)

**Decision**: All tests run offline (`fakeredis` + `EchoProvider`/recording doubles returning
`CompletionResult`; SDKs never contacted). Coverage (maps to FR-027/SC-010):

- **Chat contract** (`tests/test_chat_api.py`, extended): asserts `id`/`object`/`created`/`model`;
  `choices[0].finish_reason` normalized (double reports `length` → `"length"`; echo → `"stop"`);
  `anonymization_meta.entities_detected` per-type over a **multi-message** history with matching
  `total_entities`; `input_anonymization.pseudonymized_content` + `replacements` offsets indexing the
  **original** latest user message; `timing_ms` has all six stages and `total ≥ 0`; the **validation
  matrix** (empty messages; last role ≠ user; role `tool`; non-string content; unknown model
  `mistral-large` → 400 listing prefixes) each **preserves `session_id`** and contacts no provider; the
  EPIC 4 **no-PII** assertions still hold for the routed path; `message_count` increments only on
  success.
- **Sessions** (`test_sessions_api.py`, new): after a turn detecting two `PERSON` + one `PESEL`, `GET`
  returns `entity_count==3`, `entities_by_type=={"PERSON":2,"PESEL":1}`, `message_count==1`,
  `ttl_remaining_seconds>0`, present `created_at`/`last_activity`; `DELETE` succeeds then `GET`/`DELETE`
  → 404; unknown id → 404; a session that detected no PII → 404 on both verbs.
- **Providers** (`test_providers_api.py`, new): with `OPENAI_API_KEY` set and `ANTHROPIC_API_KEY`
  unset, the three entries carry the right `requires_key`/`key_configured`; **no key value** appears in
  the body; the endpoint answers **while Redis is down** (gate-exempt).
- **Logging** (`test_request_logging.py`, new): capture stdout for a PII-bearing chat turn → **exactly
  one** JSON line with all required fields and the six timing stages; assert the line contains **no**
  original value, **no** message content, **no** fake value (audit against the known PII/fakes); assert
  `endpoint` is the route template (no `session_id` path value); force the emit to raise and confirm the
  chat response is still 200 and the error went to stderr.
- **Pipeline inbound** (`test_pipeline_inbound.py`, new): `run_inbound` returns `entities_detected`
  summed over the whole history, `last_user_replacements` only for the last message with offsets into
  the original, and a `timing` whose three inbound stages are present/non-negative.
- **Providers/finish-reason** (`tests/llm_providers/test_*`, extended): each adapter returns
  `CompletionResult` with the right `provider` name and a normalized `finish_reason`
  (OpenAI `length`→`length`; Anthropic `max_tokens`→`length`, `end_turn`→`stop`; Ollama
  `done_reason="stop"`→`stop` and **missing** → `stop`); the router passes the `CompletionResult`
  through unchanged.

**Rationale**: Proves the full contract and the Constitution VIII no-PII-in-logs guarantee without keys
or network (FR-024/FR-027). The logging audit and the failure-injection test are the epic's critical
checks.

**Alternatives rejected**: *Live provider calls* — needs keys + network; *snapshot the whole response*
— brittle against `created`/`id`; targeted field assertions are stabler.

---

## D14 — Regression freeze, docs & Postman alignment

**Decision**:
- **Frozen**: EPIC 2/3/5 public behaviour; the Redis `fwd:/rev:/forms:/meta/corefs` layout and the
  AES-256-GCM envelope; the detection/generation layers; the EPIC 5 adapters/router and the centralized
  `kind → HTTP` map. The chat **flow** is unchanged; only `api/chat.py`'s response/validation, the port
  return type, the pipeline inbound method, and the additive store/repository methods change.
- **Existing tests** stay green except where the **port return type** changed: chat tests and provider
  tests update their doubles/assertions to `CompletionResult` (expected — the agreed extension). The
  EPIC 3 debug endpoints (`/v1/pseudonymize`, `/v1/depseudonymize`, `/v1/sessions/{id}/mappings`) are
  untouched.
- **Docs/Postman**: add requests for `GET /v1/providers`, `GET`/`DELETE /v1/sessions/{id}`, and update
  the `POST /v1/chat/completions` example to show the **full** response (id/object/created/model,
  `finish_reason`, `anonymization_meta`, `input_anonymization`). Note the new structured log line in the
  dev docs.

**Rationale**: Keeps the regression surface tight and documents the one externally-visible behavioural
change (the richer chat response + the three new endpoints).

**Alternatives rejected**: *Version the chat response behind a flag* — unnecessary for a thesis
prototype with a single in-repo client (EPIC 7); the full contract is the intended shape.
