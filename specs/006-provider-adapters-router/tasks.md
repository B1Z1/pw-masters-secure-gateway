---
description: "Task list for EPIC 5 — Provider Adapters & Model-Based Router"
---

# Tasks: EPIC 5 — Provider Adapters (Provider-Agnostic) & a Model-Based Router

**Input**: Design documents from `specs/006-provider-adapters-router/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec mandates network-free test coverage (FR-027, SC-009). All new tests mock
the OpenAI/Anthropic async SDK clients (no keys, no network) and reuse the echo/recording doubles.

**Organization**: Tasks are grouped by user story (spec priority) for independent implementation and
testing. The router class and every adapter are testable in isolation with test doubles / mocked SDKs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6 (maps to spec user stories); Setup/Foundational/Polish carry no story label
- All paths are repo-relative. Backend package: `apps/gateway-api/gateway_api/`; tests:
  `apps/gateway-api/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New dependencies + the configuration delta that the whole epic builds on.

- [X] T001 [P] Add `openai` and `anthropic` to `[project].dependencies` in `apps/gateway-api/pyproject.toml`, then `uv sync` (run from `apps/gateway-api`). If building the Docker image, rebuild with the proxy CA: `CA_CERT_FILE=~/.certs/netskope-ca.pem docker compose build gateway-api`.
- [X] T002 Apply the config delta in `apps/gateway-api/gateway_api/config.py`: REMOVE `default_llm_provider`; CHANGE `default_model` default to `"ollama/qwen2.5:3b"`; ADD `anthropic_max_tokens: int = 4096` (env `ANTHROPIC_MAX_TOKENS`). Keys/`ollama_*` unchanged. (See [data-model.md §6](./data-model.md), [research.md D9](./research.md))
- [X] T003 Update the startup log in `apps/gateway-api/gateway_api/main.py` to drop the `provider=%s` / `settings.default_llm_provider` field (keep `model`, `redis_configured`, `session_ttl`; never log secrets). (depends on T002)
- [X] T004 [P] Update `.env.example`: remove `DEFAULT_LLM_PROVIDER`; set `DEFAULT_MODEL=ollama/qwen2.5:3b`; add `ANTHROPIC_MAX_TOKENS=4096`; refresh the stale EPIC 4 comments (the `extra_hosts` note is already present and stays).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The extended error vocabulary + the single centralized `kind → HTTP` map that every adapter, the router, and the endpoint depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Extend `ProviderErrorKind` in `apps/gateway-api/gateway_api/llm_providers/base.py` to `Literal["unreachable", "missing_model", "timeout", "rate_limit", "auth", "unknown_model"]` (additive; `LLMProvider`/`ChatMessage`/`LLMProviderError` shapes otherwise unchanged — port reused per FR-001). (See [contracts/error-taxonomy.md](./contracts/error-taxonomy.md))
- [X] T006 Centralize the error map in `apps/gateway-api/gateway_api/api/chat.py`: add a module-level `_ERROR_STATUS: dict[ProviderErrorKind, int]` (`unreachable`/`missing_model`→503, `timeout`→504, `rate_limit`→429, `auth`→503, `unknown_model`→400), replace the inline `status_code = 504 if exc.kind == "timeout" else 503` with `_ERROR_STATUS.get(exc.kind, 503)`; keep `_error` preserving `session_id` and logging content-free. (depends on T005)

**Checkpoint**: Error vocabulary + central map ready — user story work can begin.

---

## Phase 3: User Story 1 - Route each request to the right provider by its model (Priority: P1) 🎯 MVP

**Goal**: An `LLMRouter` (itself an `LLMProvider`) that dispatches per request by model prefix
(`gpt-`→OpenAI, `claude-`→Anthropic, `ollama/`→Ollama with the prefix stripped), and becomes what
`get_llm_provider()` returns — with no change to the pipeline or the chat endpoint.

**Independent Test**: With each provider replaced by a recording double, route `gpt-4o`,
`claude-3-5-sonnet`, and `ollama/qwen2.5:3b`; confirm each reached the matching adapter and that the
Ollama double received `qwen2.5:3b` (prefix stripped).

### Tests for User Story 1

- [X] T007 [P] [US1] Router unit tests in `apps/gateway-api/tests/llm_providers/test_llm_router.py`: `gpt-*`→OpenAI double, `claude-*`→Anthropic double, `ollama/qwen2.5:3b`→Ollama double receives `qwen2.5:3b`; adapters built lazily and cached (factory invoked once); `health_check` delegates to the default model's provider. (See [contracts/llm-router.md](./contracts/llm-router.md))

### Implementation for User Story 1

- [X] T008 [US1] Implement `LLMRouter(LLMProvider)` in `apps/gateway-api/gateway_api/llm_providers/llm_router.py`: prefix-dispatch in `complete(messages, *, model)`, strip `ollama/` before delegating, lazy+cached factory registry, `health_check` delegating to the default model's provider, and raise `LLMProviderError(kind="unknown_model", "Unknown model '<model>'. Recognized prefixes: gpt-, claude-, ollama/")` before any adapter call. (depends on T005; satisfies the unknown-model raise used by US2)
- [X] T009 [US1] **(blocked by T013, T015 — imports the adapter classes built in Phases 5–6)** Wire `get_llm_provider()` in `apps/gateway-api/gateway_api/llm_providers/__init__.py` to build & return the `LLMRouter` with per-prefix factories (`gpt-`→`OpenAIProvider`, `claude-`→`AnthropicProvider`, `ollama/`→`OllamaProvider`) and `settings.default_model`, replacing the hardcoded `OllamaProvider`; keep `@lru_cache`; update `__all__`. (depends on T008, T013, T015)

**Checkpoint**: Routing logic complete and unit-tested via doubles; the factory returns the router (FR-018).

---

## Phase 4: User Story 2 - Unknown or absent model is handled predictably (Priority: P1)

**Goal**: An unrecognized model is a client error (400 listing the recognized prefixes, nothing sent to
any provider); a request with no model falls back to the configured default (a local Ollama model) and
is routed by its prefix.

**Independent Test**: Send model `mistral-large` → 400 listing `gpt-`, `claude-`, `ollama/`, nothing
sent; send no model → routed to the Ollama adapter via `settings.default_model`.

### Tests for User Story 2

- [X] T010 [P] [US2] Endpoint test in `apps/gateway-api/tests/test_chat_api.py`: override `get_llm_provider` with an `LLMRouter` built from recording doubles, POST a `mistral-large` model → **400** whose `detail` lists `gpt-`, `claude-`, `ollama/`; assert **no** double's `complete` was called; `session_id` preserved. (depends on T006, T008)
- [X] T011 [P] [US2] Endpoint test in `apps/gateway-api/tests/test_chat_api.py`: POST with **no** `model` field → the request reaches the Ollama recording double with model `qwen2.5:3b` (default `ollama/qwen2.5:3b` resolved by the endpoint, stripped by the router); completes with no API keys configured. (depends on T002, T008)

**Checkpoint**: Routing edges (400 + keyless default) verified; Ollama is never a silent catch-all.

---

## Phase 5: User Story 3 - Anthropic adapter converts messages to Anthropic's contract (Priority: P2)

**Goal**: An `AnthropicProvider` that lifts system content into the top-level `system` field
(concatenated; omitted when none), merges consecutive same-role turns so the history alternates
user-first, and passes an explicit `max_tokens` from config — over the async Anthropic client with no
retry.

**Independent Test**: Hand the adapter a system message + two consecutive user messages with the SDK
client mocked; assert the outgoing call has `system` set (concatenated), an alternating user-first
history (the two user messages merged), and `max_tokens` present.

### Tests for User Story 3

- [X] T012 [P] [US3] Anthropic adapter unit tests in `apps/gateway-api/tests/llm_providers/test_anthropic_provider.py` (mock `AsyncAnthropic`): system messages lifted + concatenated with `"\n\n"`; no-system case omits the `system` param; two consecutive same-role messages merged (alternating, user-first); `max_tokens` passed from config; SDK exceptions → `rate_limit`/`auth`/`missing_model`/`timeout`/`unreachable`; `messages.create` called exactly once (no retry) and **never with `stream=True`** (Constitution V — synchronous only); missing key → `auth` without building a client. (See [contracts/anthropic-adapter.md](./contracts/anthropic-adapter.md))

### Implementation for User Story 3

- [X] T013 [US3] Implement `AnthropicProvider(LLMProvider)` in `apps/gateway-api/gateway_api/llm_providers/anthropic_provider.py`: `(api_key, max_tokens)` ctor; lazy+cached `AsyncAnthropic(max_retries=0)`; the `(system, messages)` normalization; `messages.create(model, max_tokens, messages[, system])`; join text blocks; SDK-exception→`kind` mapping; missing-key→`auth` naming `ANTHROPIC_API_KEY`. (depends on T005, T002 for `anthropic_max_tokens`)

**Checkpoint**: Anthropic conversion correct and unit-tested offline.

---

## Phase 6: User Story 4 - OpenAI adapter behaviours (Priority: P2)

**Goal**: An `OpenAIProvider` that sends the native shape with no conversion (system stays first), logs
a warning + returns the partial content on a length-truncated answer, and surfaces the provider's own
error for deprecated/unknown models — over the async OpenAI client with no retry.

**Independent Test**: With the SDK client mocked, confirm a system message is sent first unchanged; a
`finish_reason == "length"` response logs a warning and still returns the partial content; a
deprecated/unknown model surfaces the SDK error.

### Tests for User Story 4

- [X] T014 [P] [US4] OpenAI adapter unit tests in `apps/gateway-api/tests/llm_providers/test_openai_provider.py` (mock `AsyncOpenAI`): native pass-through (system stays first, no conversion); `finish_reason == "length"` logs a warning (assert via `caplog`, content-free) and returns the partial content; SDK exceptions → `rate_limit`/`auth`/`missing_model`/`timeout`/`unreachable`; `chat.completions.create` called exactly once (no retry) and **never with `stream=True`** (Constitution V — synchronous only); missing key → `auth` without building a client. (See [contracts/openai-adapter.md](./contracts/openai-adapter.md))

### Implementation for User Story 4

- [X] T015 [US4] Implement `OpenAIProvider(LLMProvider)` in `apps/gateway-api/gateway_api/llm_providers/openai_provider.py`: `(api_key)` ctor; lazy+cached `AsyncOpenAI(max_retries=0)`; `chat.completions.create(model, messages)` with no conversion; length-truncation warning + partial-content return; SDK-exception→`kind` mapping (`NotFoundError`→`missing_model` carrying the SDK message); missing-key→`auth` naming `OPENAI_API_KEY`. (depends on T005)

**Checkpoint**: OpenAI adapter behaviours correct and unit-tested offline.

---

## Phase 7: User Story 5 - Provider errors map to predictable statuses (Priority: P2)

**Goal**: At the endpoint, a provider rate limit → 429 (no retry); a missing/invalid key → 503 naming
the key; startup with no keys still succeeds — all via the single centralized map.

**Independent Test**: A provider raising `kind="rate_limit"` → endpoint 429 (no retry); a provider
raising `kind="auth"` → 503 whose detail names the key; app imports/starts with no keys set.

### Tests for User Story 5

- [X] T016 [P] [US5] Endpoint test in `apps/gateway-api/tests/test_chat_api.py`: a failing provider double raising `LLMProviderError(kind="rate_limit")` → **429**; assert the provider was invoked once (no retry at the endpoint) and `session_id` preserved. (depends on T006)
- [X] T017 [P] [US5] Endpoint + startup test in `apps/gateway-api/tests/test_chat_api.py`: a provider double raising `kind="auth"` (message naming the key) → **503** with the key name in `detail` and `session_id` preserved; and assert `get_settings()`/app import succeeds with no `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` set (keys optional at startup). (depends on T006)

**Checkpoint**: 429 / 503 mapping verified end to end; keyless startup confirmed.

---

## Phase 8: User Story 6 - Ollama reused and selected explicitly (Priority: P3)

**Goal**: The reused Ollama adapter is selected explicitly by the `ollama/` prefix (stripped before
send); its EPIC 4 edge cases (unreachable/missing-model → 503, long-timeout → 504) still hold through
the router; docs/Postman move to prefixed model names.

**Independent Test**: `ollama/qwen2.5:3b` reaches the Ollama adapter with `qwen2.5:3b`; with the server
stopped/model absent → 503; past the long timeout → 504.

### Tests for User Story 6

- [X] T018 [P] [US6] Test in `apps/gateway-api/tests/llm_providers/test_llm_router.py` (extend) and/or `test_chat_api.py`: `ollama/`-prefixed model reaches the Ollama path explicitly with the prefix stripped, and the existing Ollama error kinds still surface as 503/503/504 through the router; confirm `tests/llm_providers/test_ollama_provider.py` remains unchanged and green. (depends on T008)

### Implementation / Docs for User Story 6

- [X] T019 [P] [US6] Update model names to the `ollama/` prefix in `postman/PW Masters — Secure Gateway API.postman_collection.json` ("Chat" folder), `dev/ollama/README.md`, and `.claude/rules/local-llm-ollama.md` (a bare `qwen2.5:3b` now 400s as an unknown model).

**Checkpoint**: Ollama explicit selection + stripping verified; docs aligned.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: The no-PII guarantee for the routed path, regression verification, and final validation.

- [X] T020 [P] Extend the no-PII assertions in `apps/gateway-api/tests/test_chat_api.py`: for a routed request, the messages captured by the recording provider contain only synthetic values and `caplog` contains no original PII (FR-024, SC-008, Constitution VIII). (depends on T008)
- [X] T021 Verify `docker-compose.yml` `gateway-api` already declares `extra_hosts: ["host.docker.internal:host-gateway"]` (no change expected — verify only). (See [research.md D11](./research.md))
- [X] T022 Run the full regression + lint and the quickstart: `uv run pytest` (EPIC 1–5 green; EPIC 2/3/4 suites and the Redis/AES-256-GCM formats unchanged), `uv run ruff check .`, then [quickstart.md](./quickstart.md) §1 offline checks. (depends on all prior)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately. T003 depends on T002.
- **Foundational (Phase 2)**: depends on Setup. T006 depends on T005. **Blocks all user stories.**
- **User Stories (Phase 3–8)**: all depend on Foundational. Their *tests* are independent (doubles /
  mocked SDKs); the live wiring `get_llm_provider` (T009) depends on the adapter classes (T013, T015).
- **Polish (Phase 9)**: depends on the desired stories; T022 depends on everything.

### User Story Dependencies

- **US1 (P1)**: router class + tests (T007, T008) need only Foundational. The wiring (T009) additionally
  needs the adapter classes (T013, T015) so `__init__.py` can import them.
- **US2 (P1)**: needs T006 (map) + T008 (router); uses doubles — independent of the real adapters.
- **US3 (P2)** Anthropic adapter: needs T005 (+ T002 for `max_tokens`). Independent (mocked SDK).
- **US4 (P2)** OpenAI adapter: needs T005. Independent (mocked SDK).
- **US5 (P2)**: needs T006; uses failing doubles — independent of the real adapters.
- **US6 (P3)**: needs T008; reuses the existing Ollama adapter unchanged.

### Within Each User Story

- Write the test task first (it should fail before implementation), then implement.
- `base.py` enum (T005) before adapters/router; the central map (T006) before endpoint error tests.

### Parallel Opportunities

- Setup: T001 and T004 in parallel (T002→T003 sequential).
- Once Foundational is done, the three adapters and the router class are independent:
  **T012/T013 (Anthropic), T014/T015 (OpenAI), and T007/T008 (router) can proceed in parallel.**
- US2/US5/US6 test tasks (T010, T011, T016, T017, T018) touch test files and run in parallel once their
  deps land; T020 too. (Note: tasks editing the **same** `test_chat_api.py` — T010, T011, T016, T017,
  T020 — should be coordinated or sequenced to avoid merge conflicts even though they are logically
  independent.)

---

## Parallel Example: after Foundational (Phase 2) completes

```bash
# Three independent build tracks, each network-free:
Task: "Router unit tests + LLMRouter (T007, T008) — tests/llm_providers/test_llm_router.py, gateway_api/llm_providers/llm_router.py"
Task: "Anthropic adapter + tests (T012, T013) — gateway_api/llm_providers/anthropic_provider.py"
Task: "OpenAI adapter + tests (T014, T015) — gateway_api/llm_providers/openai_provider.py"
# Then converge on the wiring:
Task: "Wire get_llm_provider -> LLMRouter (T009) — gateway_api/llm_providers/__init__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1: router class + unit tests (T007, T008) — the headline, fully testable with doubles.
3. **STOP and VALIDATE**: `uv run pytest tests/llm_providers/test_llm_router.py`.

### Runnable keyless demo (US1 + US2 through the reused Ollama)

1. Build the adapter classes (US3 T013, US4 T015) so `get_llm_provider` can import them, then wire
   T009. With `DEFAULT_MODEL=ollama/qwen2.5:3b` and a local Ollama, a no-model request round-trips with
   **no API keys** (quickstart §2a).

### Incremental Delivery

1. Setup + Foundational → routing vocabulary ready.
2. US1 (router) → US2 (edges) → demo keyless routing through Ollama.
3. US3 (Anthropic) + US4 (OpenAI) → live hosted routing.
4. US5 (error mapping) → US6 (Ollama explicit + docs) → Polish (no-PII, regression, quickstart).

---

## Notes

- [P] = different files, no incomplete-task dependencies. Tasks editing `test_chat_api.py` are logically
  independent but share a file — sequence them to avoid conflicts.
- The provider **port** (`LLMProvider`, `ChatMessage`, `LLMProviderError` shape) is reused unchanged;
  only `ProviderErrorKind` is extended (additive) — FR-001.
- No PII in logs or in any provider payload, for **every** provider (Constitution I/VIII) — asserted in
  T020 and via the reused EPIC 4 chat assertions.
- Adapters **never retry** — SDK clients built with `max_retries=0` (verified in T012/T014).
- Frozen: EPIC 2/3/4 public behaviour, the Redis `fwd:/rev:/forms:/meta` layout, the AES-256-GCM
  envelope — verified by T022.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
