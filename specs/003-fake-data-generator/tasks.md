---
description: "Task list for EPIC 3 — Fake-Data Generator & Reversible Session Mapping Store"
---

# Tasks: EPIC 3 — Realistic Fake-Data Generator and Reversible Session Mapping Store

**Input**: Design documents from `specs/003-fake-data-generator/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: INCLUDED — FR-028 mandates unit/integration tests for the generators, inflection, encryption, consistency/collision logic and the replace→restore round-trip. Test tasks are first within each story.

**Organization**: By user story (US1–US4 from spec.md). All paths are under `apps/gateway-api/`. This file **reorganizes** the plan's build-order "Implementation Phases" (0–6) into story-grouped phases; where the two differ (e.g. the plan builds inflection before the store, here inflection sits in US3 while the store core is US1), the task placement governs execution order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (setup / foundational / polish carry no story label)

## Path Conventions

Backend app `apps/gateway-api/`: source in `gateway_api/`, tests in `tests/`. New generation package: `gateway_api/pseudonym_generation/` (per-type builders in `gateway_api/pseudonym_generation/builders/`); new store package: `gateway_api/pseudonym_vault/`; thin routes in `gateway_api/api/`. Reuses Epic 2 `gateway_api/pii_detection/` and Epic 1 `gateway_api/dependencies.py` + `config.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and package skeletons.

- [x] T001 Add `faker` and `cryptography` to `apps/gateway-api/pyproject.toml` `[project].dependencies`, and `fakeredis` to `[dependency-groups].dev`; then lock + sync (`nx run gateway-api:install` or `cd apps/gateway-api && uv lock && uv sync`)
- [x] T002 [P] Create generation package skeleton: `apps/gateway-api/gateway_api/pseudonym_generation/__init__.py` and `apps/gateway-api/gateway_api/pseudonym_generation/builders/__init__.py`
- [x] T003 [P] Create store package skeleton: `apps/gateway-api/gateway_api/pseudonym_vault/__init__.py`
- [x] T004 [P] Create test package dirs: `apps/gateway-api/tests/pseudonym_generation/__init__.py` and `apps/gateway-api/tests/pseudonym_vault/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared plumbing every story builds on — the Epic-2 DTO/engine extension, the shared DTO, encryption, config, and test fixtures.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 [P] Extend `DetectedEntity` with optional `lemma: str | None = None` and `case: str | None = None` in `apps/gateway-api/gateway_api/pii_detection/dto.py` (data-model §1)
- [x] T006 Add spaCy morphology access in `apps/gateway-api/gateway_api/pii_detection/nlp.py` (obtain the spaCy `Doc` from the singleton NlpEngine) and an enrichment pass in `apps/gateway-api/gateway_api/pii_detection/engine.py` that, for kept PERSON/LOCATION entities only, fills `lemma` + `case` (`token.morph` `Case`); other types stay `None` (research D1) (depends: T005)
- [x] T007 [P] Change `redis_session_ttl` default `3600` → `1800` (30 min) in `apps/gateway-api/gateway_api/config.py` (FR-009, clarification 2026-06-16)
- [x] T008 [P] `FakeValue` DTO (`entity_type, base, forms: dict[str,str] | None, gender: str | None`) in `apps/gateway-api/gateway_api/pseudonym_generation/dto.py` (data-model §2)
- [x] T009 [P] AES-256-GCM `encrypt(bytes)->bytes` / `decrypt(bytes)->bytes` (key = 32 bytes from `REDIS_ENCRYPTION_KEY`; fresh 96-bit nonce; envelope `nonce‖ciphertext‖tag`) in `apps/gateway-api/gateway_api/pseudonym_vault/encryption.py` (research D3, contracts/encryption.md)
- [x] T010 Test fixtures in `apps/gateway-api/tests/conftest.py`: `seeded_faker` (reproducible generator), `mapping_store` factory backed by **fakeredis**, an AES key fixture, a Redis-available patch (so endpoint tests aren't 503'd by the Epic 1 gate), reusing the existing `patch_analyzer` for model-free API tests (depends: T009)

**Checkpoint**: Shared plumbing importable; encryption round-trips; `DetectedEntity` carries lemma/case.

---

## Phase 3: User Story 1 — Replace detected PII with realistic fakes and restore it (Priority: P1) 🎯 MVP

**Goal**: `POST /v1/pseudonymize` detects PII (reuse Epic 2), substitutes each entity with a realistic, checksum-valid Polish fake (correct PESEL gender, REGON variant, valid phone, ±10y date), stores the reversible mapping, and returns text + replacements + `session_id`; `POST /v1/depseudonymize` restores the originals. Empty input → empty result + session, no error; no LLM.

**Independent Test**: pseudonymize a Polish snippet (name, city, e-mail, phone, date, PESEL) → realistic type-correct checksum-valid fakes + replacement list + session_id; depseudonymize with that id → original text reconstructed; empty input → empty; logs carry no PII (quickstart V1).

### Tests for User Story 1 ⚠️

- [x] T011 [P] [US1] API round-trip tests in `apps/gateway-api/tests/test_pseudonymize_api.py` (pseudonymize→depseudonymize restores original; `session_id` created+echoed when absent; empty/whitespace → empty result + session; **no LLM/no outbound I/O**; no input/fake values in logs) using `patch_analyzer` + fakeredis
- [x] T012 [P] [US1] Person builder tests in `apps/gateway-api/tests/pseudonym_generation/test_person.py` (first+last same gender; surname is declinable; ≠ original; seed determinism)
- [x] T013 [P] [US1] Identifier builder tests in `apps/gateway-api/tests/pseudonym_generation/test_identifiers.py` (fake PESEL passes checksum + same gender + post-2000 offset; NIP valid incl. leading-zero; REGON 9/14 variant preserved & valid; bank account mod-97)
- [x] T014 [P] [US1] Contact builder tests in `apps/gateway-api/tests/pseudonym_generation/test_contact.py` (valid Polish phone format; e-mail shape)
- [x] T015 [P] [US1] Location builder tests in `apps/gateway-api/tests/pseudonym_generation/test_location.py` (realistic city; atomic address `ul. … N, NN-NNN City`)
- [x] T016 [P] [US1] Date builder tests in `apps/gateway-api/tests/pseudonym_generation/test_date_pl.py` (fake within ±10 years; valid `DD.MM.YYYY`)
- [x] T017 [P] [US1] Generator dispatch + seed-determinism tests in `apps/gateway-api/tests/pseudonym_generation/test_generator.py` (dispatch by entity_type; identical output for a fixed seed)
- [x] T018 [P] [US1] Store core tests in `apps/gateway-api/tests/pseudonym_vault/test_store.py` (get_or_create caches per exact key; get_original exact reverse lookup; writes `fwd`/`rev`/`forms`/`meta`; every op refreshes TTL) — fakeredis

### Implementation for User Story 1

- [x] T019 [P] [US1] Checksum **generation** helpers (reuse Epic 2 weight tuples): `pesel_control_digit`/`make_pesel(birth_date, gender, serial)`, `nip_control_digit`, `regon9_control_digit`, `regon14_control_digit`, `nrb_check_digits` in `apps/gateway-api/gateway_api/pii_detection/checksums.py` (contracts/generators.md)
- [x] T020 [P] [US1] Person builder (Faker `pl_PL` gendered first+last; **post-filter** surname to a declinable pattern) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/person.py`
- [x] T021 [P] [US1] Identifier builders (PESEL preserving `metadata["gender"]` + post-2000; NIP; REGON preserving `metadata["variant"]`; bank account mod-97) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/identifiers.py` (depends: T019)
- [x] T022 [P] [US1] Contact builders (realistic Polish e-mail; valid-format Polish phone) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/contact.py`
- [x] T023 [P] [US1] Location builders (city; atomic address) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/location.py`
- [x] T024 [P] [US1] Date builder (`DD.MM.YYYY`; uniform ±10-year shift of the parsed original) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/date_pl.py` (research D9)
- [x] T025 [US1] `FakeDataGenerator.generate(entity) -> FakeValue` dispatching on `entity_type`, with an injectable Faker seed; export from `pseudonym_generation/__init__.py` in `apps/gateway-api/gateway_api/pseudonym_generation/generator.py` (depends: T008, T020, T021, T022, T023, T024)
- [x] T026 [P] [US1] Mapping-key strategy — per-type `mapping_key` (lemma / `strip_separators`·`digits_only` via Epic 2 `pii_detection/normalization` / case-folded text) and the `fwd:` field name = `HMAC_SHA256(key, type|mapping_key)` — in `apps/gateway-api/gateway_api/pseudonym_vault/keys.py` (research D4, contracts/encryption.md)
- [x] T027 [P] [US1] `SessionMeta` dataclass + field-name prefixes (`fwd:`/`rev:`/`forms:`/`meta`) in `apps/gateway-api/gateway_api/pseudonym_vault/session.py` (data-model §4/§5)
- [x] T028 [US1] `MappingStore` core in `apps/gateway-api/gateway_api/pseudonym_vault/store.py`: `get_or_create` (exact `fwd` hit → cached; else generate via `FakeDataGenerator` and write `fwd`+`rev`-per-form+`forms`+`meta`, all original PII encrypted), `get_original` (exact `rev`), `extend_ttl`; sliding TTL refresh on every op; `get_mapping_store()` singleton over `get_redis_client()` (depends: T008, T009, T025, T026, T027; contracts/mapping-store.md)
- [x] T029 [US1] `POST /v1/pseudonymize` in `apps/gateway-api/gateway_api/api/pseudonymize.py`: detect via `DetectionEngine` (503 if model not ready, reuse `is_model_ready`) → `get_or_create` per entity → replace spans **end→start** → return `{pseudonymized_text, entities_replaced[], session_id}`, generating a `session_id` when absent (depends: T028; contracts/pseudonymize.openapi.yaml)
- [x] T030 [US1] `POST /v1/depseudonymize` in `apps/gateway-api/gateway_api/api/pseudonymize.py`: load session → replace fake forms with originals **longest-first**, word-boundary aware, exact `rev` lookup → return `{restored_text, session_id}`; unknown/empty session → text unchanged (depends: T028)
- [x] T031 [US1] Register the pseudonymize router in `apps/gateway-api/gateway_api/main.py` (do **not** add to `_GATE_EXEMPT_PATHS` → Redis-gated automatically); log `session_id` + entity types/counts/timings only — never originals or fakes (depends: T029, T030; Constitution VIII)

**Checkpoint**: MVP — realistic, checksum-valid substitution and a working reverse round-trip for base-form occurrences (inflection arrives in US3).

---

## Phase 4: User Story 2 — Keep substitutions consistent across a multi-turn session (Priority: P2)

**Goal**: Same original → same fake; full-name then surname-only → same fake person; genuinely different people sharing a surname root → distinct fakes; separator variants → one fake; same literal under two types → two mappings; generated fakes never collide within the session.

**Independent Test**: across one session — same original twice → same fake; "Jan Kowalski" then "Kowalski" → same person; "Anna Kowalska" vs "Jan Kowalski" → distinct; PESEL with/without dashes → one fake; same literal two types → two fakes; seeded collision → unique fallback (quickstart V2).

### Tests for User Story 2 ⚠️

- [x] T032 [P] [US2] Consistency/coreference tests in `apps/gateway-api/tests/pseudonym_vault/test_store.py` (idempotent same original→same fake; full-name→surname-only reuse; same-root distinct; **ambiguous surname matching 2+ stored people → new person**; collision retry+fallback yields a unique value) — fakeredis
- [x] T033 [P] [US2] Key-strategy tests in `apps/gateway-api/tests/pseudonym_vault/test_keys.py` (separator variants → identical `mapping_key`/HMAC → one mapping; same literal under two entity types → distinct HMAC → two mappings; HMAC field name contains no substring of the original)
- [x] T034 [P] [US2] Coreference matching tests in `apps/gateway-api/tests/pseudonym_vault/test_matching.py` (full-lemma containment scoped to the same `entity_type`; no fragment/cross-type matches)

### Implementation for User Story 2

- [x] T035 [US2] Coreference resolver — same-`entity_type` full-lemma containment; exactly-one match → reuse, two-or-more → signal "new" — in `apps/gateway-api/gateway_api/pseudonym_vault/matching.py` (research D7)
- [x] T036 [US2] Wire coreference into `get_or_create` (PERSON/LOCATION: resolve before generating; ambiguous → generate new; write a `fwd` alias on reuse) in `apps/gateway-api/gateway_api/pseudonym_vault/store.py` (depends: T028, T035)
- [x] T037 [US2] Collision-safe generation in `get_or_create`: detect a fake already used in the session, retry the generator ≤3×, then a per-type deterministic fallback (numeric suffix for IDs/email/phone; **re-roll, never a suffix, for names**) in `apps/gateway-api/gateway_api/pseudonym_vault/store.py` (depends: T028; research D6)

**Checkpoint**: Mapping is stable, coreference-aware, separator-insensitive, type-scoped, and collision-free within a session.

---

## Phase 5: User Story 3 — Handle Polish grammatical inflection in both directions (Priority: P2)

**Goal**: All inflected forms of a PERSON/LOCATION resolve to one fake; the fake is inserted in the original's grammatical case on the way out and the original restored in the matching case on the way in; first name and surname inflect independently; addresses are atomic; rare/foreign/indeclinable names fall back to base form.

**Independent Test**: "Sprawa Jana Kowalskiego z Krakowa." → fake in matching case (e.g. "…Marka Nowaka z Gdańska."); restore → original genitive forms; city oblique "w Krakowie" recognised & case-rendered; rare surname mapped consistently but shown in base form (quickstart V3).

### Tests for User Story 3 ⚠️

- [x] T038 [P] [US3] Inflection tests in `apps/gateway-api/tests/pseudonym_generation/test_inflection.py` (each pattern × six cases; INDECLINABLE → base form; independent first/last declension; city patterns; fleeting-e `Marek→Marka`, k/g softening `Anka→Ance`)
- [x] T039 [P] [US3] API inflection round-trip tests in `apps/gateway-api/tests/test_pseudonymize_api.py` (inflected full name → same fake person rendered in matching case; restore puts the original back in the matching case; oblique city; rare surname → base form)

### Implementation for User Story 3

- [x] T040 [P] [US3] `classify(name, gender) -> Pattern`, `decline(base, pattern, case) -> str`, `all_forms(base, pattern) -> {case: form}` over fixed suffix tables for {nom,gen,dat,acc,ins,loc} incl. INDECLINABLE fallback in `apps/gateway-api/gateway_api/pseudonym_generation/inflection.py` (research D2, contracts/inflection.md)
- [x] T041 [US3] Populate `FakeValue.forms` via `all_forms` (classify the generated base; first/last classified+declined independently) in `apps/gateway-api/gateway_api/pseudonym_generation/builders/person.py` and `apps/gateway-api/gateway_api/pseudonym_generation/builders/location.py` (depends: T040, T020, T023)
- [x] T042 [US3] `pseudonymize`: for PERSON/LOCATION insert the fake in the original's case via `decline(fake_base, entity.case)` (using `lemma`/`case` from T006) in `apps/gateway-api/gateway_api/api/pseudonymize.py` (depends: T029, T040)
- [x] T043 [US3] `depseudonymize`: case-aware restore — locate fake forms (incl. inflected, via `forms`/`rev`) and `decline(orig_base, matched_case)`; exact then **bounded Levenshtein ≤2** fuzzy lookup (pure-Python, in `pseudonym_vault/matching.py`) in `apps/gateway-api/gateway_api/api/pseudonymize.py` (depends: T030, T040; research D8)

**Checkpoint**: Inflected PERSON/LOCATION round-trip is grammatical in both directions; rare names degrade to base form (documented).

---

## Phase 6: User Story 4 — Securely store, expire, clear, and review session mappings (Priority: P3)

**Goal**: Originals AES-256-GCM encrypted at rest and unreadable without the key (key never exposed); TTL expiry with sliding refresh on activity; explicit clear removes all mappings at once; reviewer can list all mappings; no PII in logs; Redis restart loses the session (accepted recovery).

**Independent Test**: raw Redis shows ciphertext values + HMAC field names (no readable PII); TTL resets on activity and elapses to empty; `delete_session` empties; `get_all_mappings` returns the pairs; restart → empty session (quickstart V4).

### Tests for User Story 4 ⚠️

- [x] T044 [P] [US4] Encryption tests in `apps/gateway-api/tests/pseudonym_vault/test_encryption.py` (round-trip; two encrypts of the same plaintext → different blobs; decrypt with a wrong key fails; key asserted 32 bytes / AES-256)
- [x] T045 [P] [US4] Lifecycle + at-rest tests in `apps/gateway-api/tests/pseudonym_vault/test_store.py` (TTL set + sliding refresh; expiry → empty session; `delete_session` removes all; `get_all_mappings` lists original↔fake pairs (also reachable via the `GET /v1/sessions/{id}/mappings` debug endpoint); stored field values are ciphertext and `fwd:` names are HMAC; missing/expired hash behaves as empty — FR-027) — fakeredis

### Implementation for User Story 4

- [x] T046 [US4] `get_all_mappings(session_id)` (one `HGETALL` + decrypt → original↔fake pairs) and `delete_session(session_id)` (one `DEL`) in `apps/gateway-api/gateway_api/pseudonym_vault/store.py`, **plus** a thin debug listing endpoint `GET /v1/sessions/{session_id}/mappings` over `get_all_mappings` in `apps/gateway-api/gateway_api/api/pseudonymize.py` (Redis-gated; returns the pairs to the caller but never logs them) — gives the reviewer surface (FR-011/SC-010) a runtime entry point (depends: T028, T031; FR-010/FR-011)
- [x] T047 [US4] Audit every log statement in the store and the two endpoints — `session_id` + entity types/counts/timings only, never originals, fakes, or pairs — in `apps/gateway-api/gateway_api/pseudonym_vault/store.py` and `apps/gateway-api/gateway_api/api/pseudonymize.py` (Constitution VIII / FR-026)

**Checkpoint**: Store is encrypted, expiring, clearable, reviewable, and log-clean.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T048 [P] Document Constitution-IX limitations (no name↔PESEL gender association; no cross-field DOB coherence; inflection limited to common patterns, rare/foreign → base form; address inflection not handled / atomic; Redis restart loses the session) in `apps/gateway-api/README.md`
- [ ] T049 Run the quickstart validation scenarios V1–V6 in `specs/003-fake-data-generator/quickstart.md` against a running backend (Redis up + model loaded)
- [x] T050 [P] Lint + format: `nx run gateway-api:lint` and `nx run gateway-api:format`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks all stories** (DTO/engine extension, FakeValue, encryption, config, fixtures).
- **US1 (Phase 3)**: depends on Foundational. MVP — generators + store core + the two endpoints.
- **US2 (Phase 4)**: depends on US1's store (T028) — coreference + collision added to `store.py`.
- **US3 (Phase 5)**: depends on US1 (T029/T030 endpoints, T020/T023 builders) + T006 (lemma/case) — inflection module + case rendering.
- **US4 (Phase 6)**: depends on US1's store (T028) + foundational encryption (T009) — listing/clear + security verification.
- **Polish (Phase 7)**: depends on all targeted stories.

### User Story Dependencies

- US1 → independent (the MVP). US2, US3, US4 each **extend** the US1 store/endpoints but are independently testable: US2 = consistency (coreference/collision), US3 = inflection (case in/out), US4 = secure lifecycle (TTL/clear/list/encryption). US2/US3/US4 do not depend on one another.

### Within Each Story

- Tests first (write, see fail), then DTO/helpers → builders/modules → store wiring → routes. Identifier builders (US1) depend on the checksum generation helpers (T019).

### ⚠️ Same-file serialization (not parallel despite different stories)

- `pseudonym_vault/store.py`: T028 (US1 core), T036 + T037 (US2), T046 + T047 (US4) — run **sequentially**.
- `api/pseudonymize.py`: T029 + T030 (US1), T042 + T043 (US3), T046 (US4 list endpoint) + T047 (US4 audit) — sequential.
- `pseudonym_generation/builders/person.py` & `location.py`: T020/T023 (US1) then T041 (US3) — sequential.
- `pseudonym_vault/matching.py`: T035 (US2) then T043's fuzzy lookup (US3) — sequential.
- `pii_detection/dto.py` + `engine.py` + `nlp.py`: T005/T006 (foundational) only.
- `tests/pseudonym_vault/test_store.py`: T018 (US1), T032 (US2), T045 (US4) — sequential.
- `tests/test_pseudonymize_api.py`: T011 (US1), T039 (US3) — sequential.

### Parallel Opportunities

- Setup: T002, T003, T004 in parallel.
- Foundational: T005, T007, T008, T009 in parallel (T006 after T005; T010 after T009).
- US1 tests T011–T018 in parallel; builders T020–T024 in parallel; helpers T019, keys T026, session T027 in parallel (T025 after builders; T028 after T025/T026/T027).
- US2 tests T032–T034 in parallel. US3 tests T038–T039 in parallel. US4 tests T044–T045 in parallel.

---

## Parallel Example: User Story 1 (generators)

```bash
# Tests first (independent files):
Task: "Person builder tests in tests/pseudonym_generation/test_person.py"
Task: "Identifier builder tests in tests/pseudonym_generation/test_identifiers.py"
Task: "Contact builder tests in tests/pseudonym_generation/test_contact.py"
Task: "Location builder tests in tests/pseudonym_generation/test_location.py"
Task: "Date builder tests in tests/pseudonym_generation/test_date_pl.py"

# After T019 (checksum gen helpers), implement builders in parallel:
Task: "Person builder in gateway_api/pseudonym_generation/builders/person.py"
Task: "Identifier builders in gateway_api/pseudonym_generation/builders/identifiers.py"
Task: "Contact builders in gateway_api/pseudonym_generation/builders/contact.py"
Task: "Location builders in gateway_api/pseudonym_generation/builders/location.py"
Task: "Date builder in gateway_api/pseudonym_generation/builders/date_pl.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** (quickstart V1: realistic checksum-valid substitution + reverse round-trip via the two endpoints). Demoable substitution layer.

### Incremental Delivery

1. Setup + Foundational → encryption, DTO/engine extension, fixtures.
2. + US1 → MVP (realistic fakes + reversible store + the two endpoints).
3. + US2 → cross-turn consistency (coreference, separators, collision-free).
4. + US3 → Polish inflection both ways (the thesis-distinctive part).
5. + US4 → secure, expiring, reviewable store + log hygiene.
6. Polish → limitations doc, quickstart run, lint.

### Notes

- `[P]` = different files, no incomplete dependency. Heed the same-file serialization list above.
- Generator/inflection/encryption/key tests need **no model and no Redis**; store tests use **fakeredis**; the API round-trip test uses `patch_analyzer` (no model). A real end-to-end round-trip is in quickstart.md (`pl_core_news_lg` baked into the image; `uv run python -m spacy download pl_core_news_lg` for native dev).
- `forms` is generic in the store (T028): US1 may write `forms=None`/base-only; US3 populates `all_forms` so `rev:` gains per-case forms and the API renders case — no store rewrite needed.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- Never log input text, fakes, or original↔fake pairs (Constitution VIII) — enforced in T031/T047 and asserted in T011.
