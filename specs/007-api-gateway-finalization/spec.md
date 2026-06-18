# Feature Specification: EPIC 6 — API Gateway: Frontend-Ready Backend Surface, Logging/Metrics & Session Management

**Feature Branch**: `im/06-finalize-api`

**Created**: 2026-06-18

**Status**: Draft

**Input**: User description: "EPIC 6 — API Gateway (FastAPI): harden the Epic 4 chat round-trip into the complete, frontend-ready backend surface, and add logging/metrics and session management. Epic 6 does NOT add new anonymization logic — it HARDENS the existing HTTP surface so the React SPA (Epic 7) can be built entirely against the backend WITHOUT any further backend change. The pipeline, the mapping store, the providers and the router are REUSED, not reimplemented."

## Overview

EPIC 4 (spec 005) closed the first end-to-end LLM round-trip with a deliberately minimal
`POST /v1/chat/completions` that returned only `{session_id, choices:[{index, message,
finish_reason:null}]}`. EPIC 5 (spec 006) added a provider-agnostic adapter layer and a model-prefix
router. **EPIC 6 adds no new anonymization, detection, fake-generation, or routing logic.** It
**hardens the existing HTTP surface** into the complete backend contract a React single-page app
(EPIC 7 — a chat view, an original-vs-pseudonymized side-by-side view, a per-session statistics
dashboard, and a configuration panel) can be built against **without any further backend change**.
That "100% frontend-ready" bar is the explicit acceptance test for the epic.

The pipeline, the mapping store, the providers, and the router are **reused, not reimplemented**.
Where this epic must touch lower layers it is intentional and in scope, and limited to two agreed
extensions: the **provider port now surfaces a finish reason** (today `complete()` returns only the
assistant text, and the endpoint hardcodes `finish_reason: null`), and the **pipeline now returns
per-stage timing and per-type entity metrics** (today they are neither measured nor returned). No
other lower-layer behaviour changes.

The epic delivers four hardening tracks:

1. **The full chat-completions contract.** The same flow (pseudonymize the whole message history →
   call exactly one provider via the router → de-pseudonymize the answer) now returns the complete
   OpenAI-shaped response (`id`, `object`, `created`, `model`, `choices` with a **real**
   `finish_reason`) plus the gateway-specific extensions the frontend needs: an aggregate
   `anonymization_meta` for the dashboard and a per-current-message `input_anonymization` for the
   per-message entity info and the side-by-side view — so the SPA never has to call the debug
   `/v1/pseudonymize` endpoint.

2. **Provider discovery** (`GET /v1/providers`), a read-only endpoint that lets the configuration
   panel populate the provider choice and warn "no API key configured" **before** the first message.

3. **Logging & metrics middleware**, a separate FastAPI middleware (distinct from the EPIC 1
   Redis-availability gate) that emits exactly one structured JSON log line per request, carrying the
   per-stage timing and per-type entity counts — and provably **no** original PII, content, or fakes.

4. **Session management** (`GET` / `DELETE /v1/sessions/{session_id}`), so the dashboard can read a
   session's statistics and TTL and the configuration panel can reset a session.

All EPIC 3/4/5 guarantees hold without exception: every outgoing provider request contains only
synthetic data (Constitution I); the original↔fake mapping is AES-256 encrypted in Redis
(Constitution III); sessions expire on TTL; and **no original personal data ever appears in logs**
(Constitution VIII — a CRITICAL defect if violated). The system stays synchronous only — no
streaming/SSE (Constitution V). Authentication/authorization is out of scope for this thesis
prototype: anyone holding a `session_id` may read or delete it (a documented limitation).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drive the chat view and side-by-side view from one response (Priority: P1)

A frontend developer sends a chat turn and receives a single complete response that carries
everything the chat view and the original-vs-pseudonymized side-by-side view need, with no second
call. The response is OpenAI-shaped (`id`, `object`, `created`, `model`, `choices[0]` with the
assistant message and a real `finish_reason`) and carries the gateway extensions: `anonymization_meta`
(the aggregate counts/timing/provider for the dashboard) and `input_anonymization` (the synthetic
version of the latest user message plus the list of replacements with offsets into the original
message). The `finish_reason` is a real value reported by the provider, normalized to OpenAI
vocabulary (`stop`/`length`); a provider that cannot report one (e.g. the echo stub) yields `stop`.

**Why this priority**: This is the headline deliverable — the complete, single-call chat contract is
the foundation the entire SPA is built on. Without it the chat view, the per-message entity info, and
the side-by-side view cannot exist without extra backend calls, which the epic explicitly forbids.

**Independent Test**: With the provider replaced by a recording double that reports a known finish
reason, send a turn whose latest user message contains PII; confirm the response includes
`id` (`chatcmpl-…`), `object: "chat.completion"`, a numeric `created`, the resolved `model`,
`choices[0].finish_reason` normalized from the double's value, an `anonymization_meta` with per-type
counts over the whole history, and an `input_anonymization` whose `replacements` offsets index the
original latest user message and whose `pseudonymized_content` matches the synthetic latest message.

**Acceptance Scenarios**:

1. **Given** a valid chat turn, **When** it succeeds, **Then** the response carries `id` of the form
   `chatcmpl-<uuid>`, `object: "chat.completion"`, a unix-seconds `created`, the resolved `model`, and
   `choices[0]` = `{index:0, message:{role:"assistant", content}, finish_reason}`.
2. **Given** the request omits `model`, **When** it succeeds, **Then** the response `model` is the
   configured default model actually used (not null/empty).
3. **Given** a provider that reports a `length`-style finish reason, **When** the turn succeeds,
   **Then** `choices[0].finish_reason` is `"length"`; **Given** the echo/stub provider (cannot report
   one), **Then** `finish_reason` is `"stop"`.
4. **Given** a turn whose history contains multiple PII entities across several messages, **When** it
   succeeds, **Then** `anonymization_meta.entities_detected` is a per-type count dictionary computed
   over the WHOLE pseudonymized history of the turn, `total_entities` is its sum, and `provider` /
   `model` name the concrete provider and resolved model that served the request.
5. **Given** the latest user message contains PII, **When** the turn succeeds, **Then**
   `input_anonymization.pseudonymized_content` is the synthetic version of that latest message and
   `input_anonymization.replacements` is a list of `{entity_type, original, fake, start, end}` whose
   `start`/`end` offsets index INTO the original latest user message.
6. **Given** any successful turn, **When** the response is returned, **Then** `session_id` is the
   supplied id, or a newly generated id when none was supplied.

---

### User Story 2 - Read a session's statistics and reset it (Priority: P1)

A frontend developer powers the statistics dashboard and the configuration panel's "reset session"
control from two session endpoints. `GET /v1/sessions/{session_id}` returns the session's
`created_at`, `last_activity`, `ttl_remaining_seconds`, `entity_count`, `entities_by_type` (the
dashboard bar chart), and `message_count` (successful chat round-trips). `DELETE
/v1/sessions/{session_id}` deletes the session and all its mappings, returning success only when the
session existed. A non-existent, TTL-expired, or never-stored (no PII ever detected) session returns
404 on both verbs.

**Why this priority**: The dashboard and the session-reset control are first-class SPA features named
in the acceptance bar, and they are independently demonstrable the moment chat has run once. They
depend only on data the mapping store already persists, so they are a self-contained slice.

**Independent Test**: Run one chat turn that detects two `PERSON`s and one `PESEL`, then `GET` the
session and confirm `entity_count` = 3, `entities_by_type` = `{"PERSON":2,"PESEL":1}`, `message_count`
= 1, a positive `ttl_remaining_seconds`, and present `created_at`/`last_activity`. Then `DELETE` it
(success), `GET` it again (404), and `DELETE` it again (404). Separately `GET` a random unknown id and
confirm 404.

**Acceptance Scenarios**:

1. **Given** a session with stored mappings, **When** `GET /v1/sessions/{id}` is called, **Then** it
   returns `{session_id, created_at, last_activity, ttl_remaining_seconds, entity_count,
   entities_by_type, message_count}` where `entity_count`/`entities_by_type` are the DISTINCT
   original↔fake mappings grouped by entity type and `entity_count` is their sum.
2. **Given** a session that has had N successful chat round-trips, **When** it is read, **Then**
   `message_count` equals N and `ttl_remaining_seconds` reflects the live Redis TTL of the session.
3. **Given** an existing session, **When** `DELETE /v1/sessions/{id}` is called, **Then** the session
   and ALL its mappings are deleted and the call reports success.
4. **Given** a non-existent or TTL-expired session, **When** either `GET` or `DELETE` is called,
   **Then** the response is 404.
5. **Given** a session in which no PII was ever detected (no stored state), **When** either verb is
   called, **Then** the response is 404 ("no mappings, nothing to manage").

---

### User Story 3 - Configure the provider/model choice before the first message (Priority: P2)

A frontend developer populates the configuration panel's provider/model selection and shows a "no API
key configured" warning before the user sends anything. `GET /v1/providers` returns, for each of
`openai`, `anthropic`, and `ollama`: `name`, `requires_key` (true for openai/anthropic, false for
ollama), and `key_configured` (whether the server holds the key). API keys are server-side `.env`
only — never accepted from the client and never returned.

**Why this priority**: The configuration panel needs this to guide the user away from an
unconfigured provider before a failed first message, but the chat flow itself works without it; it is
a usability layer over the already-routed providers.

**Independent Test**: With `OPENAI_API_KEY` configured and `ANTHROPIC_API_KEY` absent, call
`GET /v1/providers` and confirm three entries; `openai` → `requires_key:true, key_configured:true`;
`anthropic` → `requires_key:true, key_configured:false`; `ollama` → `requires_key:false`. Confirm no
secret value appears anywhere in the response.

**Acceptance Scenarios**:

1. **Given** the server configuration, **When** `GET /v1/providers` is called, **Then** it returns an
   entry for each of `openai`, `anthropic`, `ollama` with `name`, `requires_key`, and `key_configured`.
2. **Given** openai and anthropic, **When** the response is built, **Then** their `requires_key` is
   true; **Given** ollama, **Then** its `requires_key` is false.
3. **Given** a provider whose key is present in the server `.env`, **When** the response is built,
   **Then** its `key_configured` is true; **Given** a provider whose key is absent, **Then** false.
4. **Given** any provider, **When** the response is built, **Then** no API key value (and no other
   secret) is present in the response body.

---

### User Story 4 - One structured, PII-free log line per request (Priority: P2)

An operator (or a reviewer auditing Constitution VIII) sees exactly one structured JSON log line per
request on stdout, emitted by a middleware distinct from the EPIC 1 Redis-availability gate. The line
carries `timestamp`, `session_id`, `endpoint`, `provider`, `model`, `entities_detected` (per-type
dict), and `timing_ms` with the per-stage breakdown (`ner_analysis`, `fake_generation`, `redis_write`,
`llm_request`, `deanonymization`, `total`). The endpoint/pipeline stash these metrics in
request-scoped state; the middleware reads and emits them. The line never contains original PII,
message content, or fake values. A logging failure never breaks the request.

**Why this priority**: Observability and the audit proof that no PII leaks to logs are required for
the thesis and for the dashboard's timing breakdown to be trustworthy, but they layer onto the chat
flow rather than enabling it.

**Independent Test**: Drive a chat turn containing PII and capture stdout; confirm exactly one JSON
line for that request with all required fields and a `timing_ms` whose stages are present and whose
`total` is consistent with the sum of stages; assert via the captured log that no original value, no
message content, and no fake value appears in it. Then force the logging step to raise and confirm the
chat response is still returned normally with the error reported to stderr.

**Acceptance Scenarios**:

1. **Given** any request, **When** it completes, **Then** exactly one structured JSON log line is
   emitted to stdout for that request by the logging/metrics middleware.
2. **Given** a chat request, **When** it is logged, **Then** the line contains `timestamp`,
   `session_id`, `endpoint`, `provider`, `model`, `entities_detected`, and `timing_ms` with stages
   `ner_analysis`, `fake_generation`, `redis_write`, `llm_request`, `deanonymization`, and `total`.
3. **Given** a request that detected and substituted PII, **When** it is logged, **Then** the line
   contains NO original value, NO message content, and NO fake value — only metadata.
4. **Given** the logging step fails (e.g. serialization error), **When** the request completes,
   **Then** the failure is caught and reported to stderr and the response is returned normally.
5. **Given** any value that could carry PII into a path or query, **When** the line is built, **Then**
   it is sanitized before logging (the architecture does not put PII in URLs).

---

### User Story 5 - Predictable validation and error contract that always preserves the session (Priority: P2)

A frontend developer relies on every error carrying back the `session_id` so a retry stays in the same
session, and on all input validation happening before any provider is contacted. An empty `messages`,
a last message whose role is not `user`, a message with a role outside {system, user, assistant} or a
missing/non-string content, and an unknown model (no recognized provider prefix) each return 400 with
a clear message — the unknown-model 400 lists the recognized prefixes. Provider failures keep the
EPIC 5 mapping (unreachable / missing model / missing-or-invalid key → 503 naming the missing key;
upstream rate limit → 429; timeout → 504). Every error body — 400/429/503/504 — preserves `session_id`.

**Why this priority**: The error contract is reused from EPIC 4/5 and largely intact; the new bar is
that the full validation set and every error body uniformly preserve `session_id`. It hardens the
chat contract from US1 but is independently testable with no successful round-trip needed.

**Independent Test**: Send each invalid request (empty messages; last role `assistant`; a message with
role `tool`; a message with non-string content; model `mistral-large`) and confirm a 400 with a clear
message (the model case listing the recognized prefixes) and a preserved `session_id`, with no
provider contacted. Then simulate each provider failure kind and confirm the documented status and a
preserved `session_id`.

**Acceptance Scenarios**:

1. **Given** an empty `messages` array, **When** the turn is submitted, **Then** the response is 400
   with a clear message and the `session_id` is preserved, and no provider is contacted.
2. **Given** a last message whose role is not `user`, **When** submitted, **Then** 400 + preserved
   `session_id`.
3. **Given** a message whose role is outside {system, user, assistant}, or whose content is missing or
   not a string, **When** submitted, **Then** 400 + preserved `session_id`.
4. **Given** a model matching no recognized provider prefix, **When** submitted, **Then** 400 whose
   message lists the recognized prefixes, with `session_id` preserved and nothing sent to any provider.
5. **Given** a provider failure (unreachable/missing-model/missing-or-invalid key → 503 naming the
   missing key; upstream 429 → 429; timeout → 504), **When** it occurs, **Then** the documented status
   is returned, the `session_id` is preserved, and inbound mappings already written to Redis are not
   rolled back.

---

### Edge Cases

- **No PII in the turn** → the chat response is well-formed with `anonymization_meta.entities_detected`
  = `{}`, `total_entities` = 0, and `input_anonymization.replacements` = `[]`; the timing stages still
  appear; the session may legitimately have no stored state.
- **`model` omitted** → the resolved default model appears in `model`, `anonymization_meta.model`, and
  the log line; routing uses the default's prefix (EPIC 5).
- **Echo/stub or any provider that cannot report a finish reason** → `finish_reason` is `"stop"`.
- **Provider reports a length-truncated answer** → `finish_reason` is `"length"` and the partial
  content is still returned (EPIC 5 behaviour preserved).
- **`entities_detected` scope** → counted over the WHOLE pseudonymized history of the turn, not just
  the latest user message; `input_anonymization` covers ONLY the latest user message.
- **Session never had PII** → `GET`/`DELETE /v1/sessions/{id}` return 404 (no mappings to manage).
- **TTL-expired session** → treated as non-existent: 404 on `GET` and `DELETE`.
- **`DELETE` of an already-deleted session** → 404 on the second call.
- **Provider with no key configured** → `GET /v1/providers` reports `key_configured:false`; a chat
  turn routed to it still fails on first use with 503 naming the key (EPIC 5).
- **Logging failure** → caught, reported to stderr, the request response is unaffected.
- **PII that could reach a path/query** → sanitized before logging; the architecture does not place
  PII in URLs.
- **Redis unavailable** → the EPIC 1 gate 503s the request before the chat flow; the session endpoints
  (which need Redis) are likewise gated.
- **Two middlewares** → the Redis-availability gate and the logging/metrics middleware are distinct and
  do not duplicate each other's responsibility.

## Requirements *(mandatory)*

### Functional Requirements

#### A. Full chat-completions response contract

- **FR-001**: `POST /v1/chat/completions` MUST keep the EPIC 4/5 flow unchanged — pseudonymize the
  WHOLE message history → call exactly one provider via the EPIC 5 router → de-pseudonymize the
  answer — and MUST add no new anonymization, detection, generation, or routing logic.
- **FR-002**: A successful response MUST include `id` of the form `chatcmpl-<uuid>`, `object` =
  `"chat.completion"`, `created` as a unix timestamp in seconds, and `model` = the resolved model
  actually used (the request's `model`, or the configured default model when the request omits it).
- **FR-003**: A successful response MUST include `choices[0]` = `{index, message:{role:"assistant",
  content}, finish_reason}`, where `finish_reason` is a REAL value reported by the provider normalized
  to OpenAI vocabulary (`"stop"`, `"length"`); a provider/model that cannot report one (e.g. the
  echo/stub) MUST yield `"stop"`.
- **FR-004**: A successful response MUST include `session_id` = the supplied id, or a newly generated
  id when none was supplied.
- **FR-005**: A successful response MUST include `anonymization_meta` containing: `entities_detected`
  (a per-type count dictionary computed over the WHOLE pseudonymized history of this turn, not just
  the latest user message), `total_entities` (the sum of those counts), `provider` (the concrete
  provider that served the request — `"openai"`/`"anthropic"`/`"ollama"`), `model` (the resolved
  model), `processing_time_ms` (total gateway wall-clock for the request), and `timing_ms` (the same
  per-stage timing object emitted to the logs, so the dashboard can show the breakdown without parsing
  logs).
- **FR-006**: A successful response MUST include `input_anonymization` for the CURRENT (latest) user
  message: `pseudonymized_content` (the synthetic version of that message) and `replacements` (a list
  of `{entity_type, original, fake, start, end}` whose `start`/`end` offsets index INTO the ORIGINAL
  latest user message — exactly what the inbound pipeline already produces). Returning originals here
  is acceptable: the client↔gateway hop is the trusted hop; only the gateway↔provider hop is protected.

#### B. Request validation and centralized error contract

- **FR-007**: All request validation MUST run BEFORE any provider call and MUST return HTTP 400 with a
  clear message for: empty `messages`; a last message whose role is not `user`; any message whose role
  is outside {system, user, assistant} or whose content is missing or not a string.
- **FR-008**: An unknown model (no recognized provider prefix) MUST surface as HTTP 400 whose message
  lists the recognized prefixes; this decision comes from the EPIC 5 router and the contract guarantees
  it surfaces as 400 here, before any provider is contacted.
- **FR-009**: Provider-error mapping MUST stay centralized and unchanged from EPIC 5: provider
  unreachable / missing model / missing-or-invalid key → 503 (naming the missing key); upstream rate
  limit (429) → 429; timeout → 504.
- **FR-010**: EVERY error body (400/429/503/504) MUST preserve `session_id` so the client can retry in
  the same session; inbound mappings already written to Redis on a failing turn MUST NOT be rolled back.

#### C. Provider discovery

- **FR-011**: `GET /v1/providers` MUST be a read-only endpoint returning, for each of `openai`,
  `anthropic`, and `ollama`: `name`, `requires_key` (true for openai/anthropic, false for ollama), and
  `key_configured` (whether the corresponding key is present in the server `.env`).
- **FR-012**: API keys MUST be server-side `.env` only — never accepted from the client and never
  returned by any endpoint (no key value or other secret appears in the `/v1/providers` response).

#### D. Logging & metrics middleware

- **FR-013**: A FastAPI middleware DISTINCT from the EPIC 1 Redis-availability gate MUST emit exactly
  ONE structured JSON log line per request to stdout; the two middlewares MUST NOT duplicate each
  other's responsibility.
- **FR-014**: The log line MUST contain `timestamp`, `session_id`, `endpoint`, `provider`, `model`,
  `entities_detected` (per-type dict), and `timing_ms` with the per-stage breakdown `ner_analysis`,
  `fake_generation`, `redis_write`, `llm_request`, `deanonymization`, and `total`.
- **FR-015**: The endpoint/pipeline MUST stash these metrics in request-scoped state and the middleware
  MUST read and emit them (the pipeline is extended to measure and return per-stage timing and per-type
  entity counts; this is the agreed pipeline extension).
- **FR-016**: The log line MUST NEVER contain original PII, message content, or fake values — only
  metadata (Constitution VIII). Any value that could carry PII into a path or query MUST be sanitized
  before logging.
- **FR-017**: A logging failure MUST NOT break the request: it MUST be caught, reported to stderr, and
  the response returned normally.

#### E. Session management

- **FR-018**: `GET /v1/sessions/{session_id}` MUST return `{session_id, created_at, last_activity,
  ttl_remaining_seconds, entity_count, entities_by_type, message_count}`.
- **FR-019**: `entity_count` and `entities_by_type` MUST be the DISTINCT original↔fake mappings in the
  session grouped by entity type, with `entity_count` equal to their sum; `message_count` MUST be the
  number of successful chat round-trips in the session (incremented by 1 per successful
  `POST /v1/chat/completions`); `ttl_remaining_seconds` MUST come from the live Redis TTL of the session.
- **FR-020**: `DELETE /v1/sessions/{session_id}` MUST delete the session and ALL its mappings and
  report success ONLY when the session existed.
- **FR-021**: A non-existent, TTL-expired, or never-stored (no PII ever detected) session MUST return
  404 on both `GET` and `DELETE`.

#### F. Cross-cutting (reuse + agreed extensions + constitution guarantees)

- **FR-022**: The provider port MUST be extended to surface a finish reason from `complete()` (replacing
  EPIC 4's hardcoded `null`); this is the agreed port extension and is the source of the normalized
  `finish_reason` in FR-003. No other port behaviour changes.
- **FR-023**: The pipeline, the mapping store, the providers, and the EPIC 5 router MUST be REUSED, not
  reimplemented; the ONLY lower-layer changes permitted are the finish-reason port extension (FR-022)
  and the pipeline timing/entity-metric extension (FR-015).
- **FR-024**: Every outgoing provider request MUST contain only synthetic data and no original personal
  data MUST appear in any log (Constitution I, VIII); the original↔fake mapping MUST stay AES-256
  encrypted in Redis and sessions MUST expire on TTL (Constitution III).
- **FR-025**: The flow MUST remain synchronous (request-response); the full answer MUST be received
  before de-pseudonymization. Streaming/SSE remains a deliberate non-goal (Constitution V).
- **FR-026**: No endpoint MUST require authentication or authorization; anyone holding a `session_id`
  may `GET`/`DELETE` it — a documented prototype limitation.
- **FR-027**: The full contract (FR-001..FR-026) MUST be covered by tests that run without network
  access (provider clients replaced by recording/echo doubles, Redis replaced by a fake): the complete
  chat response shape with a real normalized `finish_reason`, the whole-history `entities_detected`,
  the per-stage `timing_ms`, the per-current-message `input_anonymization` with correct offsets, the
  validation/error matrix with preserved `session_id`, `GET`/`DELETE /v1/sessions/{id}` (including the
  404 cases), `GET /v1/providers`, and the single PII-free structured log line.

### Key Entities *(include if feature involves data)*

- **Chat completion response**: The complete OpenAI-shaped success body plus gateway extensions —
  `id`, `object`, `created`, `model`, `choices` (with a real normalized `finish_reason`), `session_id`,
  `anonymization_meta`, and `input_anonymization`. The single object the SPA chat and side-by-side
  views consume.
- **Anonymization meta (aggregate)**: The dashboard summary for a turn — `entities_detected` (per-type
  counts over the whole history), `total_entities`, `provider`, `model`, `processing_time_ms`, and
  `timing_ms` (the per-stage breakdown).
- **Input anonymization (per current message)**: `pseudonymized_content` of the latest user message
  plus `replacements` (`{entity_type, original, fake, start, end}` with offsets into the original
  latest user message). What the per-message entity info and side-by-side view render.
- **Per-stage timing breakdown (`timing_ms`)**: `ner_analysis`, `fake_generation`, `redis_write`,
  `llm_request`, `deanonymization`, and `total` — emitted identically in the response and in the log.
- **Provider descriptor**: One per provider in `GET /v1/providers` — `name`, `requires_key`,
  `key_configured`; never any key value.
- **Session summary**: The `GET /v1/sessions/{id}` body — `created_at`, `last_activity`,
  `ttl_remaining_seconds`, `entity_count`, `entities_by_type`, `message_count`. Built from the
  distinct mappings and session metadata the store already persists.
- **Structured request log record**: The one-per-request JSON line — `timestamp`, `session_id`,
  `endpoint`, `provider`, `model`, `entities_detected`, `timing_ms` — metadata only, no PII/content/fakes.
- **Error body**: A failure response (400/429/503/504) that always carries `session_id` plus a clear
  message; the unknown-model 400 lists the recognized prefixes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can drive the FULL frontend feature set — chat with per-message entity info,
  the original-vs-pseudonymized side-by-side, the per-session statistics dashboard, and the
  configuration panel (provider/model selection, key-presence warning, session reset) — using ONLY the
  endpoints in this epic, with zero backend changes required.
- **SC-002**: Every successful `POST /v1/chat/completions` response carries the complete contract: a
  `chatcmpl-` id, `object`/`created`/`model`, a real normalized `finish_reason`, a per-type
  `entities_detected` over the whole history with a matching `total_entities`, the per-stage
  `timing_ms`, `processing_time_ms`, and an `input_anonymization` for the latest user message whose
  replacement offsets index the original message.
- **SC-003**: For a turn whose history holds N entities of known types, `anonymization_meta.
  entities_detected` reports exactly those per-type counts, `total_entities` equals N, and
  `input_anonymization.replacements` covers exactly the latest user message's entities.
- **SC-004**: A provider that reports a length-truncated answer yields `finish_reason:"length"`; a
  provider that cannot report one yields `"stop"`.
- **SC-005**: `GET /v1/sessions/{id}` returns the session's `created_at`, `last_activity`, a live
  `ttl_remaining_seconds`, `entity_count`/`entities_by_type` matching the distinct stored mappings, and
  a `message_count` equal to the number of successful round-trips; `DELETE` removes the session and its
  mappings; and both verbs return 404 for a non-existent, TTL-expired, or never-stored session.
- **SC-006**: `GET /v1/providers` returns the three providers with correct `requires_key`
  (openai/anthropic true, ollama false) and `key_configured` reflecting the server `.env`, and exposes
  no key value.
- **SC-007**: Exactly one structured JSON log line is emitted per request, carrying the per-stage
  timing and per-type entity counts, and an audit of that line proves it contains no original PII, no
  message content, and no fake value; a forced logging failure does not change the request's response.
- **SC-008**: Every error response (400 for empty messages / bad last role / bad message / unknown
  model listing the prefixes; 429 rate limit; 503 unreachable/missing-model/missing-key naming the key;
  504 timeout) preserves `session_id`, and validation 400s contact no provider.
- **SC-009**: Every outgoing provider request contains only synthetic values and no original personal
  data appears in any log, for every provider (Constitution I, VIII).
- **SC-010**: The full contract above is covered by passing tests that run without network access.

## Assumptions

- **Layer boundary**: This epic delivers only the HTTP-surface hardening (full chat response contract,
  `/v1/providers`, the logging/metrics middleware, and the session `GET`/`DELETE` endpoints) plus the
  two agreed lower-layer extensions (the provider-port finish reason and the pipeline timing/entity
  metrics). The detection (EPIC 2), generation + store (EPIC 3), pipeline (EPIC 4), and adapters +
  router (EPIC 5) are reused unchanged otherwise.
- **`finish_reason` normalization**: Provider finish reasons are normalized to OpenAI vocabulary, with
  `stop` and `length` as the values this epic guarantees; any other provider value is mapped to the
  closest of these (defaulting to `stop`), and a provider that cannot report one yields `stop`. The
  exact mapping table is a plan-phase detail consistent with EPIC 5's existing length-truncation
  handling.
- **`entities_detected` vs `input_anonymization` scope**: `anonymization_meta.entities_detected` counts
  over the WHOLE pseudonymized history of the turn (every message re-pseudonymized this turn);
  `input_anonymization` describes ONLY the latest user message. Counting follows what the inbound
  pipeline detects per message this turn; the dedup/counting rule across repeated entities is a
  plan-phase detail (the natural reading is per detected occurrence per message).
- **`message_count` semantics**: Incremented by 1 per SUCCESSFUL `POST /v1/chat/completions` only;
  failed turns and the debug `/v1/pseudonymize` endpoint do not increment it. The session metadata
  already persists `message_count`; this epic populates it on success. **Reconciliation with the
  never-stored-session rule**: the counter lives in the session metadata, which exists only once PII
  has been detected at least once in the session. So "+1 per success" applies to sessions that have
  stored state; a session whose *only* activity was PII-free successful turns has no stored state and
  is therefore unmanageable (404 on GET/DELETE) — its successful turns are not separately observable.
  This is the deliberate trade-off the never-stored-session 404 edge case implies (see also FR-019/FR-021).
- **Session state source**: `created_at`, `last_activity`, `entity_count`, and `message_count` come
  from the session metadata the mapping store already persists; `entities_by_type` is derived from the
  distinct stored mappings (the store already exposes all original↔fake pairs per session);
  `ttl_remaining_seconds` is the live Redis TTL of the session hash. No new persisted fields beyond
  what is needed to populate the above.
- **404 for stateless sessions**: A session is "manageable" only if it has stored mappings/metadata in
  Redis. A session id that was used but detected no PII has no stored state, so `GET`/`DELETE` return
  404 by design — an accepted limitation, not an error.
- **Logging scope**: The structured JSON middleware emits one line for every request; for non-chat
  requests (e.g. `/health`, `/v1/detect`, `/v1/providers`, session endpoints) the chat-specific fields
  (`provider`, `model`, `entities_detected`, the chat timing stages) are absent or null, while
  `timestamp`, `endpoint`, and `total` timing are always present. Whether the existing
  Redis-gate's plain log line is folded into this JSON line is a plan-phase cleanup detail, but the
  structured JSON line is the canonical per-request log and there is exactly one of it per request.
- **`timing_ms` stage mapping**: `ner_analysis` = PII detection, `fake_generation` = minting/looking up
  fakes, `redis_write` = persisting mappings, `llm_request` = the provider round-trip, `deanonymization`
  = restoring originals in the answer, `total` = end-to-end gateway wall-clock; the exact instrumentation
  points within the reused pipeline/store are a plan-phase detail.
- **Provider key variable names**: `key_configured` reflects the presence of the server-side settings
  the gateway already reads (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`); Ollama needs no key. The default
  model is an `ollama/`-prefixed local model, so the keyless offline demo works out of the box.
- **No model enumeration in `/v1/providers`**: Consistent with EPIC 5's prefix-based routing (no
  model-name registry), `/v1/providers` exposes providers and key presence, not a catalog of model
  names; the configuration panel offers provider/prefix selection and free-text model entry.
- **Out of scope (explicit)**: streaming/SSE (Constitution V); authentication/authorization on any
  endpoint (documented prototype limitation); token `usage` accounting in the response; per-request
  API-key headers (keys are `.env`-only); and any new anonymization/detection/generation/routing logic
  (EPICs 2–5, reused as-is apart from the two agreed extensions).
- **Trusted demo context**: As in EPIC 4/5, the gateway runs in a trusted/development context for the
  thesis demonstration; the no-PII-in-logs and no-PII-to-provider rules still hold without exception
  (Constitution I, VIII). The target use case remains Polish civil-law contracts.
