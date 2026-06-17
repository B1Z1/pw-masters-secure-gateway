---
description: "Task list for EPIC 4 — Anonymization Pipeline & First End-to-End LLM Round-Trip"
---

# Tasks: EPIC 4 — Anonymization Pipeline & First End-to-End LLM Round-Trip

**Input**: Design documents from `specs/005-anonymization-pipeline/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec mandates them (FR-027) and the test strategy is fixed in research D10.
Write each test task FIRST and confirm it FAILS before implementing.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each story is an
independently testable increment. Paths are relative to the repo root; backend package is
`apps/gateway-api/gateway_api`, tests under `apps/gateway-api/tests`.

**Naming rule**: all new Python must follow `.claude/rules/python-naming-conventions.md` (role-revealing
module/identifier names; no `utils`/`helpers`/`store`/`manager`).

**Regression contract (do NOT break)**: EPIC 3 public behaviour, the Redis `fwd:/rev:/forms:/meta`
layout, and the AES-256-GCM envelope are frozen. `/v1/pseudonymize` + `/v1/depseudonymize` and all
existing tests stay green. The only EPIC 3 touch-points are the additive `restore_text(…, fuzzy=False)`
flag and delegating `pseudonymize.py`'s inbound to the pipeline (response preserved).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story phases only)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New package skeletons. No new dependencies — `httpx`, `pytest-asyncio`
(`asyncio_mode = "auto"`), and `fakeredis` are already in `apps/gateway-api/pyproject.toml`.

- [ ] T001 [P] Create the pipeline package `apps/gateway-api/gateway_api/pipeline/__init__.py`
- [ ] T002 [P] Create the providers package `apps/gateway-api/gateway_api/llm_providers/__init__.py` (empty for now; `get_llm_provider` added in US1/US4)
- [ ] T003 [P] Create test package inits `apps/gateway-api/tests/pipeline/__init__.py` and `apps/gateway-api/tests/llm_providers/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The provider port and the deterministic test double — every user story depends on these.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [ ] T004 Implement the provider port in `apps/gateway-api/gateway_api/llm_providers/base.py`: `ChatMessage` (pydantic `{role: str, content: str}`), abstract `LLMProvider` (`async complete(messages: list[ChatMessage], *, model: str) -> str`, `async health_check() -> bool`), and `LLMProviderError(Exception)` with `kind: Literal["unreachable", "missing_model", "timeout"]` — per [contracts/llm-provider-port.md](./contracts/llm-provider-port.md) and data-model §4
- [ ] T005 Implement `EchoProvider` in `apps/gateway-api/gateway_api/llm_providers/echo_provider.py` (deterministic, network-free: `complete` returns the last user message's content; `health_check` → `True`) — depends on T004

**Checkpoint**: Provider port + echo double ready.

---

## Phase 3: User Story 1 - End-to-end pseudonymized chat round-trip (Priority: P1) 🎯 MVP

**Goal**: A single-turn Polish chat request runs inbound → (stub) LLM → outbound; the provider sees
only synthetic values and the returned answer has the originals restored, plus the session_id.

**Independent Test**: Send a one-message conversation (person + city + PESEL) with `fakeredis` and the
echo/stub provider; capture the provider payload (only fakes) and assert the restored answer and the
returned session_id; empty / non-user-last requests return 400.

### Tests for User Story 1 (write first, must fail)

- [ ] T006 [P] [US1] Pipeline round-trip test in `apps/gateway-api/tests/pipeline/test_anonymization_pipeline.py`: `pseudonymize_messages` → `EchoProvider.complete` → `depseudonymize_text` restores originals; assert the messages handed to the provider contain NO original PII
- [ ] T007 [P] [US1] Chat endpoint happy-path + 400 tests in `apps/gateway-api/tests/test_chat_api.py` (stub provider via FastAPI dependency override + `fakeredis`): single-turn person+city+PESEL restored, session_id generated/returned; empty `messages` → 400; last message not `role=="user"` → 400; assert no original PII in the outgoing payload or `caplog`

### Implementation for User Story 1

- [ ] T008 [US1] Implement `AnonymizationPipeline` in `apps/gateway-api/gateway_api/pipeline/anonymization_pipeline.py`: `pseudonymize_text(session_id, text) -> (fake_text, list[Replacement])` (extract the inbound body — detect via `get_engine()` → `store.get_or_create` per entity → reverse-order splice → `Replacement` list), `pseudonymize_messages(session_id, messages)` (every message's content, roles preserved), `depseudonymize_text(session_id, text)` (calls `store.restore_text` exact for now). **Log metadata only** — `session_id`, entity types/counts, timings; never log message content, originals, or fakes (Constitution VIII, FR-024) — per [contracts/anonymization-pipeline.md](./contracts/anonymization-pipeline.md)
- [ ] T009 [P] [US1] Add `get_pipeline()` factory in `apps/gateway-api/gateway_api/pipeline/anonymization_pipeline.py` building the pipeline from `get_engine()` + `get_mapping_store()` (returns None/raises so the handler can 503 when the store/model is not ready)
- [ ] T010 [US1] Refactor `apps/gateway-api/gateway_api/api/pseudonymize.py` to delegate the inbound substitution to `pipeline.pseudonymize_text`, preserving `PseudonymizeResponse` (offsets into ORIGINAL text, ordering); `/v1/depseudonymize` unchanged — `tests/test_pseudonymize_api.py` must stay green (FR-003) — depends on T008
- [ ] T011 [P] [US1] Add `get_llm_provider()` dependency in `apps/gateway-api/gateway_api/llm_providers/__init__.py` returning `EchoProvider()` (US4 switches the default to Ollama)
- [ ] T012 [US1] Implement `POST /v1/chat/completions` in `apps/gateway-api/gateway_api/api/chat.py`: `ChatCompletionRequest`/`Response` models (request carries `messages`, optional `session_id`, optional `model`), validate (400 empty / non-user-last) before any provider call, `session_id = request.session_id or uuid4().hex`, resolve `model = request.model or settings.default_model`, build pipeline via `get_pipeline()` (503 when store/model not ready), provider via `Depends(get_llm_provider)`, run `pseudonymize_messages` → `provider.complete(..., model=model)` → `depseudonymize_text`, return `{session_id, choices:[{index, message, finish_reason: null}]}`. **Log metadata only** — `session_id`, entity types/counts, status, timings; never log message content, originals, or fakes (Constitution VIII, FR-024) — per [contracts/chat-endpoint.md](./contracts/chat-endpoint.md) — depends on T008, T009, T011
- [ ] T013 [US1] Wire `chat_router` into `apps/gateway-api/gateway_api/main.py` (include_router; do NOT add to `_GATE_EXEMPT_PATHS` — it requires Redis) — depends on T012

**Checkpoint**: US1 fully functional — the headline round-trip works with the deterministic provider.

---

## Phase 4: User Story 2 - Multi-turn history re-pseudonymized consistently (Priority: P2)

**Goal**: Every turn, the WHOLE messages array is pseudonymized before the LLM call (including earlier
de-pseudonymized assistant messages), deterministically (same original → same fake).

**Independent Test**: Run a two-turn conversation in one session where turn 2 resends an earlier
assistant message containing PII; capture the turn-2 provider payload and assert every original is
replaced and each maps to the same fake it got on turn 1.

### Tests for User Story 2 (write first, must fail)

- [ ] T014 [P] [US2] Multi-turn determinism test in `apps/gateway-api/tests/test_chat_api.py`: two turns, one session; turn 2 includes an earlier assistant message with original PII; assert the full history is pseudonymized, the provider payload holds no originals, and each original maps to the same fake across turns

### Implementation for User Story 2

- [ ] T015 [US2] Verification + guard in `apps/gateway-api/gateway_api/api/chat.py`: the multi-turn property is **delivered by US1's `pseudonymize_messages`** (T008) — this task confirms the endpoint forwards the ENTIRE pseudonymized array to `provider.complete` (not only the last message) and de-pseudonymizes only the returned assistant answer for display, then adds an inline comment documenting the trust boundary (client↔gateway trusted; gateway↔LLM protected). No new pipeline logic — depends on T012

**Checkpoint**: US1 + US2 both work; multi-turn leakage path is closed and proven.

---

## Phase 5: User Story 3 - Fuzzy fallback restores inflected fakes safely (Priority: P2)

**Goal**: After the exact + inflection pass, a bounded, type-scoped fuzzy fallback recovers unforeseen
inflected fake PERSON/LOCATION tokens in base form — never firing on identifiers/email/phone, never
restoring an invented name, never re-touching a restored span.

**Independent Test**: Feed the outbound stage an answer that inflects a fake surname/city in an
unforeseen form (restored in base form); a perturbed fake identifier/email/phone (NOT fuzzed); a
look-alike non-PII token and an invented name (untouched); an ambiguous tie (skipped).

### Tests for User Story 3 (write first, must fail)

- [ ] T016 [P] [US3] Fuzzy unit tests in `apps/gateway-api/tests/pseudonym_vault/test_fuzzy_restoration.py`: inflected PERSON/LOCATION recovered in base form; exact-only enforcement (perturbed `PESEL`/`IBAN`/`POLISH_BANK_ACCOUNT`/`EMAIL_ADDRESS`/`PHONE_NUMBER`/`DATE_TIME` NOT fuzzed); prefix-anchor rejects a look-alike non-PII token; invented name passes through; unresolvable tie → skip; already-restored span untouched; token shorter than 4 not matched — per data-model §3 and research D3
- [ ] T017 [P] [US3] Add a guard test in `apps/gateway-api/tests/pseudonym_vault/test_mapping_store.py` asserting `restore_text` WITHOUT the `fuzzy` flag is byte-identical to current behaviour (regression contract)

### Implementation for User Story 3

- [ ] T018 [P] [US3] Implement the prefix-overlap helper + `FuzzyNameRestorer` in `apps/gateway-api/gateway_api/pseudonym_vault/fuzzy_restoration.py`: word-boundary token pass, min length 4, shared-prefix ratio ≥ 0.6 of the shorter token, `bounded_levenshtein(..., max_distance=2)` final gate, deterministic best match with tie → skip, token-aligned restore of the original in nominative form (D4); `NameFake` candidates built from the PERSON/LOCATION reverse records — **match against the stored fake FORMS (every per-case surface), not just the nominative base, so distance ≤ 2 holds for unforeseen oblique cases** — research D2–D4
- [ ] T019 [US3] Add additive `fuzzy: bool = False` to `MappingStore.restore_text` in `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py`: when `True`, after the unchanged exact loop, build name records from `self._repository.reverse_records` filtered to `{PERSON, LOCATION}` and run `FuzzyNameRestorer`; default keeps current behaviour — depends on T018
- [ ] T020 [US3] Switch `AnonymizationPipeline.depseudonymize_text` to call `store.restore_text(session_id, text, fuzzy=True)` in `apps/gateway-api/gateway_api/pipeline/anonymization_pipeline.py` — depends on T019

**Checkpoint**: US1–US3 work; the real restore path is robust to unforeseen LLM inflections.

---

## Phase 6: User Story 4 - Real local LLM via provider port + graceful failure (Priority: P2)

**Goal**: The chat endpoint talks to a real local Ollama server through the port and fails gracefully
(503/504, session_id preserved) when it is unreachable, missing its model, or slow.

**Independent Test**: Stub a provider that raises `kind="unreachable"`/`"missing_model"` → 503 and
`kind="timeout"` → 504, each preserving session_id; unit-test the Ollama adapter's error mapping with
mocked `httpx` (no network); confirm the same endpoint still works with the echo provider.

**Note**: the **400** validation paths (empty array / non-user-last) are delivered in **US1** (T007/T012);
US4 adds only the provider error mapping (503/504). US4 therefore depends on US1.

### Tests for User Story 4 (write first, must fail)

- [ ] T021 [P] [US4] Ollama adapter tests in `apps/gateway-api/tests/llm_providers/test_ollama_provider.py` (mocked `httpx`, no network): `ConnectError`/`ConnectTimeout` → `kind="unreachable"`; 404 / "model not found" body → `kind="missing_model"`; `ReadTimeout`/`TimeoutException` → `kind="timeout"`; `complete` parses `message.content`; `health_check` hits `/api/tags`
- [ ] T022 [P] [US4] Chat error-path tests in `apps/gateway-api/tests/test_chat_api.py` (stub provider raising each kind): unreachable → 503, missing_model → 503, timeout → 504; assert `session_id` present in every error body

### Implementation for User Story 4

- [ ] T023 [P] [US4] Add `ollama_timeout: float = 60.0` (`OLLAMA_TIMEOUT`) to `Settings` in `apps/gateway-api/gateway_api/config.py` (`ollama_base_url`/`default_model` already exist)
- [ ] T024 [US4] Implement `OllamaProvider` in `apps/gateway-api/gateway_api/llm_providers/ollama_provider.py`: `complete` → `POST {OLLAMA_BASE_URL}/api/chat` `{model, messages, stream: false}` with `timeout=OLLAMA_TIMEOUT`, returning `message.content`; `health_check` → `GET {OLLAMA_BASE_URL}/api/tags`; map exceptions to `LLMProviderError(kind=…)` per research D6/D7 — depends on T004, T023
- [ ] T025 [US4] Switch `get_llm_provider()` in `apps/gateway-api/gateway_api/llm_providers/__init__.py` to return `OllamaProvider`, keeping `EchoProvider` available for test overrides. **`DEFAULT_LLM_PROVIDER` is intentionally NOT consulted this epic** — the endpoint talks to Ollama directly; the model-based provider router is a later epic (add a code comment to that effect) — depends on T024
- [ ] T026 [US4] Add `LLMProviderError` handling in `apps/gateway-api/gateway_api/api/chat.py`: map `kind` unreachable/missing_model → 503 and timeout → 504, with a readable `detail` and the `session_id` preserved in the error body — depends on T012

**Checkpoint**: All four user stories independently functional; live Ollama round-trip demonstrable.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T027 [P] Add `OLLAMA_TIMEOUT` to the LLM block of `.env.example` (the file exists with `OLLAMA_BASE_URL`/`DEFAULT_LLM_PROVIDER`/`DEFAULT_MODEL` but lacks the timeout), and note in `apps/gateway-api/README.md` that `DEFAULT_MODEL` must name an installed Ollama model for the live demo
- [ ] T028 [P] Verify naming-rule compliance (`.claude/rules/python-naming-conventions.md`) and run `ruff` (E/F/UP/B/SIM/I) across the new `pipeline/`, `llm_providers/`, and `fuzzy_restoration.py` modules
- [ ] T029 Run the full offline suite `uv run pytest` from `apps/gateway-api` (all epics green; EPIC 3 regression intact) and execute [quickstart.md](./quickstart.md) §1
- [ ] T030 (Optional, requires Ollama) Run the live round-trip in [quickstart.md](./quickstart.md) §2 and confirm originals restored while the Ollama payload held only synthetic values; check logs carry no original PII

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: after Setup — BLOCKS all user stories (T004 → T005).
- **US1 (P3)**: after Foundational — the MVP; everything else builds on the pipeline + endpoint.
- **US2 (P4)**: after US1 (uses `pseudonymize_messages` + the endpoint).
- **US3 (P5)**: after US1 (extends the pipeline's outbound + `restore_text`). Independent of US2/US4.
- **US4 (P6)**: after US1 (real provider + endpoint error mapping). Independent of US2/US3.
- **Polish (P7)**: after the desired stories.

### Cross-story file touch-points (avoid conflicts)

- `api/chat.py`: created in US1 (T012), hardened in US2 (T015), error-mapped in US4 (T026) — sequential, not parallel across these.
- `pipeline/anonymization_pipeline.py`: US1 (T008) then US3 (T020) — sequential.
- `llm_providers/__init__.py`: US1 (T011) then US4 (T025) — sequential.
- `tests/test_chat_api.py`: US1 (T007), US2 (T014), US4 (T022) — different phases.

### Parallel opportunities

- Setup T001–T003 together.
- After US1 ships, **US2, US3, and US4 can proceed in parallel** (largely disjoint files: US3 in `pseudonym_vault/`, US4 in `llm_providers/` + `config.py`, US2 a focused test + chat guard).
- Test tasks marked [P] within a story run together (e.g. T021 + T022; T016 + T017).
- Polish T027 + T028 together.

---

## Parallel Example: after the MVP (US1) is green

```bash
# Three developers pick up the P2 stories simultaneously:
Dev A → US3: T016, T017, T018 (tests + FuzzyNameRestorer in pseudonym_vault/fuzzy_restoration.py)
Dev B → US4: T021, T023, T024 (ollama tests + config + OllamaProvider)
Dev C → US2: T014 (multi-turn test) then T015 (chat full-array guard)
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** the round-trip with
the echo provider (quickstart §1). This alone proves the gateway end-to-end without a live LLM.

### Incremental delivery

US1 (MVP, deterministic round-trip) → US2 (multi-turn safety) → US3 (robust fuzzy restore) → US4 (real
Ollama + graceful errors). Each adds value without breaking the previous; the EPIC 3 regression suite
stays green throughout.

---

## Notes

- Tests are written first and must fail before implementation (spec FR-027).
- `[P]` = different files, no incomplete dependency.
- Keep the exact + inflection restore pass first and unchanged; fuzzy is fallback-only (FR-008).
- No original PII in any provider payload or log line (Constitution I/VIII) — asserted in T006, T007,
  T014, T022.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
