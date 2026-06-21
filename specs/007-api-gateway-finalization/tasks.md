---
description: "Task list for EPIC 6 — API Gateway Finalization (frontend-ready surface, logging/metrics, sessions)"
---

# Tasks: EPIC 6 — API Gateway: Frontend-Ready Backend Surface, Logging/Metrics & Session Management

**Input**: Design documents from `specs/007-api-gateway-finalization/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec mandates network-free coverage of the full contract (FR-027, SC-010).
All tests use `fakeredis` + the reused `EchoProvider` / recording doubles (now returning
`CompletionResult`); no keys, no network. Logs are asserted via `caplog`/captured stdout for the
Constitution VIII no-PII proof.

**Organization**: Tasks are grouped by user story (spec priority) for independent implementation and
testing. **No new dependency and no config change** — the chat *flow* is reused; only the response
shape, three new endpoints, and one middleware are added, plus the two agreed extensions (the provider
port finish-reason and the pipeline timing/entity metrics).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 (maps to spec user stories); Setup/Foundational/Polish carry no story label
- All paths are repo-relative. Backend package: `apps/gateway-api/gateway_api/`; tests:
  `apps/gateway-api/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The one new package scaffold. No new dependency, no config change (verify only).

- [x] T001 [P] Create the observability package `apps/gateway-api/gateway_api/observability/__init__.py` (empty package marker). Confirm — no edit — that `apps/gateway-api/pyproject.toml` needs **no** new dependency and `config.py` / `.env.example` need **no** new setting (the epic reuses existing settings; see [data-model.md §8](./data-model.md)).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The provider-port finish-reason extension (a codebase-wide breaking change to
`complete()`'s return type) and the request-scoped metrics container. Both must land coherently before
the chat contract (US1) and the logging middleware (US4) can be built. US2/US3/US5 do not functionally
depend on these but require the suite to stay coherent.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Extend the provider port in `apps/gateway-api/gateway_api/llm_providers/base.py`: add a frozen `CompletionResult{content: str, finish_reason: str, provider: str}` and a pure `normalize_finish_reason(raw: str | None) -> str` (`stop`/`length`→same; `end_turn`/`stop_sequence`→`stop`; `max_tokens`→`length`; anything else/`None`→`stop`); change `LLMProvider.complete` return annotation `-> str` to `-> CompletionResult`. `ChatMessage`/`LLMProviderError`/`ProviderErrorKind` UNCHANGED. (See [data-model.md §2](./data-model.md), [research.md D1/D2](./research.md))
- [x] T003 [P] Update `OpenAIProvider.complete` in `apps/gateway-api/gateway_api/llm_providers/openai_provider.py` to return `CompletionResult(content=choices[0].message.content or "", finish_reason=normalize_finish_reason(choices[0].finish_reason), provider="openai")`; KEEP the length-truncation warning + partial-content behaviour. (depends on T002)
- [x] T004 [P] Update `AnthropicProvider.complete` in `apps/gateway-api/gateway_api/llm_providers/anthropic_provider.py` to return `CompletionResult(content=<joined text blocks>, finish_reason=normalize_finish_reason(response.stop_reason), provider="anthropic")`. (depends on T002)
- [x] T005 [P] Update `OllamaProvider.complete` in `apps/gateway-api/gateway_api/llm_providers/ollama_provider.py` to return `CompletionResult(content=message.content, finish_reason=normalize_finish_reason(response.json().get("done_reason")), provider="ollama")` (missing `done_reason`→`"stop"`). (depends on T002)
- [x] T006 [P] Update `EchoProvider.complete` in `apps/gateway-api/gateway_api/llm_providers/echo_provider.py` to return `CompletionResult(content=<last user message>, finish_reason="stop", provider="echo")`. (depends on T002)
- [x] T007 [P] Update `LLMRouter.complete` return annotation `-> CompletionResult` in `apps/gateway-api/gateway_api/llm_providers/llm_router.py` (pure pass-through of the inner adapter's result; `unknown_model` raise unchanged). (depends on T002)
- [x] T008 [P] Implement `apps/gateway-api/gateway_api/observability/request_metrics.py`: a `RequestMetrics` holding the six stage accumulators (`ner_analysis`, `fake_generation`, `redis_write`, `llm_request`, `deanonymization`, `total`) + `session_id`/`provider`/`model`/`entities_detected`, a `time_stage(name)` context manager, a `to_timing_ms()` / `processing_time_ms` finalizer, and a `contextvars.ContextVar` **inbound redis-write sink** with `set_inbound_redis_sink(...)` / `add_inbound_redis_write(seconds)` helpers (no-op when no sink active). (See [data-model.md §7](./data-model.md), [research.md D4/D11](./research.md))
- [x] T009 Bridge the existing chat round-trip to the new return type in `apps/gateway-api/gateway_api/api/chat.py`: `result = await provider.complete(...)`; use `result.content` for de-pseudonymization (leave the rest of the EPIC 4 minimal response as-is for now). Keeps the EPIC 4/5 chat suite green until US1 replaces this with the full contract (T016). (depends on T002)
- [x] T010 Update existing provider/router/chat tests to the new return type so the suite stays green, and assert provider-level finish-reason normalization: in `apps/gateway-api/tests/llm_providers/test_openai_provider.py`, `test_anthropic_provider.py`, `test_ollama_provider.py`, `test_llm_router.py` assert `complete` returns `CompletionResult` with the right `provider` and a normalized `finish_reason` (OpenAI `length`→`length`; Anthropic `max_tokens`→`length`, `end_turn`→`stop`; Ollama `done_reason="stop"`→`stop` and **missing**→`stop`; router passes through); update the recording double(s) in `tests/test_chat_api.py` to return `CompletionResult`. (depends on T003–T007, T009)

**Checkpoint**: `complete()` returns `CompletionResult` everywhere; the metrics container exists; the
full suite (incl. the bridged chat round-trip) is green. Story work can begin.

---

## Phase 3: User Story 1 - Drive the chat view and side-by-side view from one response (Priority: P1) 🎯 MVP

**Goal**: `POST /v1/chat/completions` returns the complete OpenAI-shaped body (`id`/`object`/`created`/
`model`/`choices` with a **real, normalized** `finish_reason`) plus `session_id`, `anonymization_meta`
(per-type counts over the whole history, totals, provider, model, `processing_time_ms`, `timing_ms`),
and `input_anonymization` (the latest user message's synthetic text + replacements with offsets into
the original) — in one call, no debug endpoint needed.

**Independent Test**: With a recording double returning `CompletionResult(finish_reason="length")`, send
a multi-message turn whose latest user message contains PII; assert `id`(`chatcmpl-…`), `object`,
`created`, resolved `model`, `choices[0].finish_reason=="length"` (echo→`"stop"`),
`anonymization_meta.entities_detected` per-type over the whole history with matching `total_entities`,
`timing_ms` with all six stages, and `input_anonymization.replacements` offsets indexing the **original**
latest user message.

### Tests for User Story 1

- [x] T011 [P] [US1] Chat contract tests in `apps/gateway-api/tests/test_chat_api.py`: override `get_llm_provider` with a recording double returning `CompletionResult`; assert the full body shape (`id` prefix `chatcmpl-`, `object=="chat.completion"`, numeric `created`, resolved `model`), `choices[0].finish_reason` normalized (`length`→`"length"`; echo→`"stop"`), `anonymization_meta.entities_detected` per-type **over a multi-message history** + `total_entities` == sum, `timing_ms` has the six stages with `total>=0` and `processing_time_ms==timing_ms.total`, `input_anonymization.pseudonymized_content` + `replacements` offsets indexing the ORIGINAL latest user message; `session_id` returned (supplied or generated); `message_count` increments on success. (See [contracts/chat-completions.md](./contracts/chat-completions.md)) (depends on T016)
- [x] T012 [P] [US1] Pipeline inbound tests in `apps/gateway-api/tests/test_pipeline_inbound.py`: `run_inbound` returns `entities_detected` summed over the whole history (per occurrence per message), `last_user_replacements` only for the last message with offsets into the original, and an `InboundTiming` whose three inbound stages are present/non-negative. (depends on T013)

### Implementation for User Story 1

- [x] T013 [US1] In `apps/gateway-api/gateway_api/pipeline/anonymization_pipeline.py`: add `InboundResult{fake_messages, entities_detected, total_entities, last_user_pseudonymized, last_user_replacements, timing}` and `InboundTiming{ner_analysis_ms, fake_generation_ms, redis_write_ms}`; make `pseudonymize_text` record `ner_analysis` (around `engine.detect`) and the substitution time (around the `get_or_create` loop) into the active `RequestMetrics` (no-op when none); add `run_inbound(session_id, messages)` that activates the inbound redis-write sink, loops via `pseudonymize_text`, aggregates per-type counts + the last message's synthetic text/replacements, derives `fake_generation = substitution − redis_write`, and returns `InboundResult`; REMOVE `pseudonymize_messages`. (See [data-model.md §3](./data-model.md), [research.md D3/D4](./research.md)) (depends on T008)
- [x] T014 [US1] Add the inbound redis-write timing hook in `apps/gateway-api/gateway_api/pseudonym_vault/session_mapping_repository.py`: wrap the inbound write ops (`write_mapping`, `write_exact_reverse`, `append_coref`, `bump_meta`, `extend_ttl`) so each adds its Redis-call duration to the active inbound redis-write sink (no-op when inactive); no public signature change. (depends on T008; **coordinate with T018 — same file**)
- [x] T015 [US1] Add `message_count` bump: `repository.bump_message_count(session_id)` (read `meta`; if present, write back `message_count+1`; **no-op when `meta` absent** so PII-free sessions stay stateless) in `session_mapping_repository.py`, and `MappingStore.increment_message_count(session_id)` delegating to it in `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py`. (See [research.md D7](./research.md)) (**coordinate with T014/T018/T019 — same files**)
- [x] T016 [US1] Rewrite the success response in `apps/gateway-api/gateway_api/api/chat.py`: add the response models (`Choice` with `finish_reason: str`, `TimingBreakdown`, `AnonymizationMeta`, `InputAnonymization`, full `ChatCompletionResponse{id,object,created,model,choices,session_id,anonymization_meta,input_anonymization}`); take the Starlette `Request`, get-or-create `RequestMetrics` on `request.state.gateway_metrics` (so US1 works with or without the US4 middleware); call `run_inbound` (records inbound stages + entities + last-message data), time `llm_request` around `provider.complete` (use `result.content/finish_reason/provider`), time `deanonymization` around `depseudonymize_text`, finalize `total`; build the response with the **same** `timing_ms` object stashed in `request.state`; call `increment_message_count` on success; `id="chatcmpl-"+uuid4().hex`, `object="chat.completion"`, `created=int(time.time())`, `model`=resolved (un-stripped). Supersedes the T009 bridge. (See [contracts/chat-completions.md](./contracts/chat-completions.md), [data-model.md §1](./data-model.md)) (depends on T002, T008, T013, T014, T015; **same file as T026 — sequence T026 after**)

**Checkpoint**: The full chat response works end-to-end (timing/entities/`finish_reason`/`input_anonymization`) via doubles — MVP runnable; chat tests green.

---

## Phase 4: User Story 2 - Read a session's statistics and reset it (Priority: P1)

**Goal**: `GET /v1/sessions/{session_id}` returns the dashboard statistics (`created_at`,
`last_activity`, `ttl_remaining_seconds`, `entity_count`, `entities_by_type`, `message_count`) and
`DELETE /v1/sessions/{session_id}` resets the session; both return 404 for non-existent / TTL-expired /
never-stored sessions.

**Independent Test**: After a turn detecting 2×PERSON + 1×PESEL, `GET` shows `entity_count==3`,
`entities_by_type=={"PERSON":2,"PESEL":1}`, `message_count==1`, `ttl_remaining_seconds>0`; `DELETE`
succeeds, then `GET`/`DELETE` → 404; unknown id → 404; a PII-free session → 404 on both verbs.

### Tests for User Story 2

- [x] T017 [P] [US2] Sessions tests in `apps/gateway-api/tests/test_sessions_api.py` (fakeredis + recording double): run a turn detecting 2×PERSON + 1×PESEL, then `GET /v1/sessions/{id}` → `entity_count==3`, `entities_by_type=={"PERSON":2,"PESEL":1}`, `message_count==1`, `ttl_remaining_seconds>0`, present `created_at`/`last_activity`; `DELETE` → 200, then `GET`/`DELETE` → 404; unknown id → 404; a turn with **no** PII → both verbs 404. (See [contracts/sessions.md](./contracts/sessions.md)) (depends on T020)

### Implementation for User Story 2

- [x] T018 [US2] Add read/lifecycle methods in `apps/gateway-api/gateway_api/pseudonym_vault/session_mapping_repository.py`: `read_meta(session_id) -> dict | None`, `ttl_seconds(session_id) -> int` (`redis.ttl`), and change `delete(session_id)` to return `bool` (`redis.delete(key) == 1`). (See [data-model.md §4](./data-model.md)) (**coordinate with T014/T015 — same file**)
- [x] T019 [US2] Add session-summary methods in `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py`: `get_session_summary(session_id) -> dict | None` (`read_meta`→`None` ⇒ `None`; group `get_all_mappings` by `entity_type` into `entities_by_type` with `entity_count`=sum; attach `created_at`/`last_activity`/`message_count` from meta + `ttl_remaining_seconds`), and change `delete_session(session_id)` to return `bool` (delegate to `repository.delete` + discard the in-process session lock). (See [research.md D8](./research.md)) (depends on T018; **coordinate with T015 — same file**)
- [x] T020 [US2] Create `apps/gateway-api/gateway_api/api/sessions.py`: `GET /v1/sessions/{session_id}` returning the `SessionSummaryResponse` (404 when `get_session_summary` is `None`) and `DELETE /v1/sessions/{session_id}` (404 when `delete_session` reports the key did not exist); `include_router` in `apps/gateway-api/gateway_api/main.py`. NOT gate-exempt (needs Redis). Coexists with the EPIC 3 `GET /v1/sessions/{id}/mappings`. (depends on T019; **coordinate main.py with T022/T024**)

**Checkpoint**: Dashboard statistics + reset work, including the full 404 matrix.

---

## Phase 5: User Story 3 - Configure the provider/model choice before the first message (Priority: P2)

**Goal**: `GET /v1/providers` lists `openai`/`anthropic`/`ollama` with `requires_key` and
`key_configured` so the config panel can warn before the first message; no key value ever leaves the
server; works while Redis is down.

**Independent Test**: With `OPENAI_API_KEY` set and `ANTHROPIC_API_KEY` unset, the three entries carry
the right `requires_key`/`key_configured`; no secret in the body; the endpoint answers while Redis is
down.

### Tests for User Story 3

- [x] T021 [P] [US3] Providers tests in `apps/gateway-api/tests/test_providers_api.py`: with `OPENAI_API_KEY` configured and `ANTHROPIC_API_KEY` absent, `GET /v1/providers` → three entries (`openai` requires_key/key_configured true; `anthropic` requires_key true / key_configured false; `ollama` requires_key false); assert **no** key value appears in the body; assert the endpoint returns 200 even when Redis is unavailable (gate-exempt). (See [contracts/providers.md](./contracts/providers.md)) (depends on T022)

### Implementation for User Story 3

- [x] T022 [US3] Create `apps/gateway-api/gateway_api/api/providers.py`: `GET /v1/providers` building the three `{name, requires_key, key_configured}` entries from `Settings` (`bool(openai_api_key)` / `bool(anthropic_api_key)`; ollama `requires_key=false`), never returning a key value; `include_router` in `apps/gateway-api/gateway_api/main.py` and add `"/v1/providers"` to `_GATE_EXEMPT_PATHS`. (See [research.md D9](./research.md)) (**coordinate main.py with T020/T024**)

**Checkpoint**: Provider discovery populates the config panel; key-safe; degraded-stack friendly.

---

## Phase 6: User Story 4 - One structured, PII-free log line per request (Priority: P2)

**Goal**: A separate, outermost middleware emits exactly one structured JSON line per request
(`timestamp`, `session_id`, `endpoint`=route template, `provider`, `model`, `entities_detected`,
`timing_ms`), provably free of PII/content/fakes, with a logging failure that never breaks the request.

**Independent Test**: A PII-bearing chat turn produces exactly one JSON line with the six timing stages
and no original/content/fake values; `endpoint` is the route template; a forced emit failure leaves the
chat response 200 (error to stderr).

### Tests for User Story 4

- [x] T023 [P] [US4] Logging middleware tests in `apps/gateway-api/tests/test_request_logging.py` (capture stdout): a PII-bearing chat turn → **exactly one** JSON line with `timestamp`, `session_id`, `endpoint`, `provider`, `model`, `entities_detected`, and `timing_ms` (six stages); audit that the line contains **no** original value, **no** message content, **no** fake value; assert `endpoint` is the route template (no path-param value); patch the emit to raise and confirm the chat response is still 200 and the error went to stderr. (See [contracts/logging-middleware.md](./contracts/logging-middleware.md)) (depends on T024)

### Implementation for User Story 4

- [x] T024 [US4] Implement the middleware in `apps/gateway-api/gateway_api/observability/request_logging.py`: create a `RequestMetrics` on `request.state.gateway_metrics` before `call_next`; after the response, finalize `total` and emit one JSON line to **stdout** (`endpoint` = matched route template, e.g. `request.scope["route"].path`, falling back to the raw path; chat fields from `request.state.gateway_metrics`; `null`/`{}` for non-chat) wrapped in `try/except` → **stderr** on failure (FR-017). Register it in `apps/gateway-api/gateway_api/main.py` so it is the **outermost** middleware (added after the `redis_availability_gate`) and **remove** the gate's plain `logger.info("request path=…")` line so there is exactly one per-request log line. (See [research.md D10/D12](./research.md)) (depends on T008; **coordinate main.py with T020/T022**)

**Checkpoint**: One PII-free structured log line per request, including gated 503s; failure-safe.

---

## Phase 7: User Story 5 - Predictable validation and error contract that always preserves the session (Priority: P2)

**Goal**: All input validation runs before any provider call and returns 400 with a clear message; the
unknown-model 400 lists the recognized prefixes; provider failures keep the EPIC 5 mapping; **every**
error body (400/429/503/504) preserves `session_id`.

**Independent Test**: Each invalid request (empty messages; last role ≠ user; role `tool`; non-string
content; model `mistral-large`) → 400 with a clear message (model case lists the prefixes) and a
preserved `session_id`, no provider contacted; each provider failure → its documented status with
`session_id` preserved.

### Tests for User Story 5

- [x] T025 [P] [US5] Validation/error tests in `apps/gateway-api/tests/test_chat_api.py`: empty `messages` → 400; last role ≠ `user` → 400; a message role `tool` → 400; non-string `content` → 400; model `mistral-large` → 400 listing `gpt-`,`claude-`,`ollama/`; each preserves `session_id` and contacts **no** provider; provider doubles raising `rate_limit`/`auth`/`timeout` → 429/503(naming the key)/504 with `session_id` preserved; inbound mappings written on a failing turn are not rolled back. (See [contracts/chat-completions.md](./contracts/chat-completions.md)) (depends on T026; **same file as T011 — coordinate**)

### Implementation for User Story 5

- [x] T026 [US5] Harden validation in `apps/gateway-api/gateway_api/api/chat.py`: replace the strict `messages: list[ChatMessage]` with a permissive `ChatInputMessage{role: str | None = None, content: Any = None}` so bad input is a handler 400 (not a pre-handler 422); validate in order — non-empty `messages`; every message `role ∈ {system,user,assistant}` and `content` a non-`None` `str`; last role `user` — each returning `_error(400, …, session_id)` before any provider call; convert valid messages to `ChatMessage`; reuse `_ERROR_STATUS` for `unknown_model`/provider errors; ensure every error body preserves `session_id` with no rollback of inbound mappings. (See [research.md D6](./research.md), [data-model.md §1](./data-model.md)) (depends on T016)

**Checkpoint**: Full validation matrix → 400 + `session_id`, no provider contacted; provider errors mapped with `session_id` preserved.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: The Constitution VIII no-PII proof across the routed path + log line, docs alignment, and
full regression/validation.

- [x] T027 [P] No-PII cross-check: extend `apps/gateway-api/tests/test_chat_api.py` / `tests/test_request_logging.py` so that for a routed PII-bearing turn the messages captured by the recording provider contain **only synthetic values** and the emitted log line + `caplog` contain **no** original PII, **no** content, **no** fake value (FR-016/FR-024, SC-009, Constitution VIII). (depends on T011, T023)
- [x] T028 [P] Docs/Postman alignment (D14): add requests for `GET /v1/providers` and `GET`/`DELETE /v1/sessions/{session_id}`, and update the `POST /v1/chat/completions` example to the **full** response (id/object/created/model, `finish_reason`, `anonymization_meta`, `input_anonymization`) in `postman/PW Masters — Secure Gateway API.postman_collection.json`; note the new structured log line in the dev docs (e.g. `README`/`docs`).
- [x] T029 Run the full regression + lint + quickstart: `uv run pytest` (EPIC 1–6 green; EPIC 2/3/5 behaviour and the Redis `fwd:/rev:/forms:/meta/corefs` + AES-256-GCM formats unchanged), `uv run ruff check .`, then [quickstart.md](./quickstart.md) §1 offline checks. (depends on all prior)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. T003–T007 + T008 depend on T002; T009 depends on T002;
  T010 depends on T003–T007 + T009. **Blocks all user stories.**
- **User Stories (Phase 3–7)**: all depend on Foundational. US1 builds the metrics/pipeline/response;
  US2/US3/US4/US5 are largely independent (US4 reads what US1 stashes but is testable on its own;
  non-chat requests still log).
- **Polish (Phase 8)**: depends on the desired stories; T029 depends on everything.

### User Story Dependencies

- **US1 (P1)** — full chat response: needs T002 (port), T008 (metrics), and its own T013–T016. MVP.
- **US2 (P1)** — sessions: needs the store/repo methods (T018, T019) and the router (T020). Independent
  of US1's response logic; shares `session_mapping_repository.py`/`mapping_store.py` with US1 (T014/T015)
  and `main.py` with US3/US4.
- **US3 (P2)** — providers: needs only T022 (+ config reads). Independent; shares `main.py`.
- **US4 (P2)** — logging: needs T008 (metrics). The middleware is testable independently; full
  chat-field assertions also exercise US1's endpoint. Shares `main.py`.
- **US5 (P2)** — validation: layers onto US1's `chat.py` (T016) — sequence after US1.

### Within Each User Story

- Write the test task first (it should fail before implementation), then implement.
- Models/value objects before the services/endpoints that use them; the central `_ERROR_STATUS` map and
  `_error` helper are reused unchanged.

### Shared-file coordination (same file, logically independent — sequence to avoid conflicts)

- `session_mapping_repository.py`: **T014** (US1 timing hook) + **T018** (US2 reads) + **T015** (US1 bump).
- `mapping_store.py`: **T015** (US1 increment) + **T019** (US2 summary/delete).
- `api/chat.py`: **T009** (bridge) → **T016** (US1 full response) → **T026** (US5 validation).
- `main.py`: **T020** (US2 router) + **T022** (US3 router+gate-exempt) + **T024** (US4 middleware).
- `tests/test_chat_api.py`: **T010** (foundational) + **T011** (US1) + **T025** (US5) + **T027** (polish).

### Parallel Opportunities

- Setup T001 alone.
- Foundational: after T002, the adapters **T003/T004/T005/T006/T007** and the metrics module **T008**
  run in parallel (different files); then T009 (bridge) and T010 (test updates).
- After Foundational, four build tracks proceed largely in parallel (coordinating the shared files
  above): **US1** (T013→T014/T015→T016), **US2** (T018→T019→T020), **US3** (T022), **US4** (T024).
- All story test tasks marked [P] (T011, T012, T017, T021, T023, T025) run in parallel once their
  implementation deps land.

---

## Parallel Example: after Foundational (Phase 2) completes

```bash
# US1 inbound + response track:
Task: "Pipeline run_inbound + InboundResult (T013) — gateway_api/pipeline/anonymization_pipeline.py"
Task: "Chat full response + metrics wiring (T016) — gateway_api/api/chat.py"
# US2 sessions track (coordinate repo/store edits with US1):
Task: "Repo read_meta/ttl/delete-bool + store get_session_summary (T018, T019) — pseudonym_vault/"
Task: "api/sessions.py GET/DELETE + main include (T020) — gateway_api/api/sessions.py"
# US3 providers track:
Task: "api/providers.py + gate-exempt (T022) — gateway_api/api/providers.py"
# US4 logging track:
Task: "request_logging middleware outermost (T024) — gateway_api/observability/request_logging.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational (port `CompletionResult` + metrics; suite green via the bridge).
2. Phase 3 US1: `run_inbound` + the full chat response (T013–T016) with contract tests (T011, T012).
3. **STOP and VALIDATE**: `uv run pytest tests/test_chat_api.py tests/test_pipeline_inbound.py` — the
   complete chat contract works via doubles. The chat view + side-by-side view can now be built.

### Incremental Delivery

1. Setup + Foundational → port + metrics ready.
2. US1 (full chat response) → MVP; the SPA chat + side-by-side are unblocked.
3. US2 (sessions) → the dashboard + session-reset are unblocked.
4. US3 (providers) → the config panel's provider/key warning is unblocked.
5. US4 (logging) → the audit-able per-request log line + dashboard timing trust.
6. US5 (validation) → the hardened error contract preserving `session_id`.
7. Polish → no-PII proof, docs/Postman, full regression + quickstart.

### Parallel Team Strategy

After Foundational, one developer takes US1 (the response + metrics), another US2 (sessions), another
US3 + US4 (providers + logging). US5 follows US1 on `chat.py`. Coordinate edits to the shared files
listed above.

---

## Notes

- [P] = different files, no incomplete-task dependencies. Tasks touching the same file (see
  "Shared-file coordination") are logically independent but must be sequenced to avoid conflicts.
- **No new dependency, no config change** — the epic reuses existing settings and components.
- The chat *flow* (pseudonymize whole history → one provider via the router → de-pseudonymize) is
  **unchanged**; only `api/chat.py`'s response/validation, the port return type, the pipeline inbound
  method, and the additive store/repository methods change.
- **Constitution VIII (CRITICAL)**: no original PII, content, or fake values in any log line —
  `endpoint` is the route template (no path-param values); proven in T023/T027.
- **Frozen** (verified by T029): EPIC 2/3/5 public behaviour, the Redis `fwd:/rev:/forms:/meta/corefs`
  layout, the AES-256-GCM envelope, and the EPIC 5 adapter/router internals (apart from the
  `CompletionResult` return). `message_count` (already in `SessionMeta`) is now incremented; no new
  persisted field.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
