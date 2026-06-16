---
description: "Task list for EPIC 2 — PII Detection Engine"
---

# Tasks: EPIC 2 — PII Detection Engine for Polish Civil-Law Contracts

**Input**: Design documents from `specs/002-pii-detection-engine/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: INCLUDED — the spec quality bar (FR-029) mandates positive/negative/edge unit tests for every custom recognizer. Test tasks are first within each story.

**Organization**: By user story (US1–US5 from spec.md). All paths are under `apps/gateway-api/`. This file **reorganizes** the plan's build-order "Implementation Phases" (0–6) into story-grouped phases (1–8); where the two differ (e.g. plan groups `checksums.py` under its Phase 1, here it sits in US2 as T026 since only US2 uses it), the task placement governs execution order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (setup / foundational / polish carry no story label)

## Path Conventions

Backend app `apps/gateway-api/`: source in `gateway_api/`, tests in `tests/`. New detection package: `gateway_api/detection/` (recognizers in `gateway_api/detection/recognizers/`); thin route in `gateway_api/api/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and package skeleton.

- [ ] T001 Add `presidio-analyzer` and `pyyaml` to `apps/gateway-api/pyproject.toml` `[project].dependencies`, then lock + sync (`nx run gateway-api:install` or `cd apps/gateway-api && uv lock && uv sync`)
- [ ] T002 [P] Create detection package skeleton: `apps/gateway-api/gateway_api/detection/__init__.py`, `apps/gateway-api/gateway_api/detection/recognizers/__init__.py`, `apps/gateway-api/gateway_api/api/__init__.py`
- [ ] T003 [P] Create test package dir `apps/gateway-api/tests/detection/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared engine plumbing every story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 [P] Define `DetectedEntity` pydantic DTO (`entity_type, start, end, score, text, metadata`) in `apps/gateway-api/gateway_api/detection/dto.py` (data-model §1)
- [ ] T005 [P] Scoring constants (`S_VALID=0.80, S_INVALID=0.30`, base bands) + `clamp_score()` to `[0.0, 0.99]` in `apps/gateway-api/gateway_api/detection/scoring.py` (data-model §5, research D6)
- [ ] T006 [P] Normalization helpers (strip spaces/dashes for validation; preserve the original span/offsets) in `apps/gateway-api/gateway_api/detection/normalization.py` (research D, FR-003/FR-013)
- [ ] T007 [P] spaCy NLP engine provider with **NKJP→Presidio label mapping** (`persName`→PERSON, `placeName`/`geogName`→LOCATION, `date`/`time`→DATE_TIME), process-singleton model loader that **lazily loads on first `detect()`** (so US1 is demoable before US5 wires eager startup load), and `is_model_ready()` in `apps/gateway-api/gateway_api/detection/nlp.py` (research D1/D2/D8)
- [ ] T008 Threshold loader with **mtime live-reload** + per-type/default post-filter, plus shipped `apps/gateway-api/gateway_api/detection/default_thresholds.yaml` in `apps/gateway-api/gateway_api/detection/thresholds.py` (contracts/thresholds.md, research D5)
- [ ] T009 [P] Add optional `DETECTION_THRESHOLDS_PATH` setting in `apps/gateway-api/gateway_api/config.py` (override path for T008)
- [ ] T010 `DetectionEngine` core in `apps/gateway-api/gateway_api/detection/engine.py`: build `AnalyzerEngine` (nlp + empty custom registry hook), `detect(text)` = analyze → map to `DetectedEntity` (`text=input[start:end]`) → clamp → threshold post-filter; export from `detection/__init__.py` (depends: T004, T005, T007, T008)
- [ ] T011 Detection test fixtures in `apps/gateway-api/tests/conftest.py`: engine fixture, `is_model_ready` monkeypatch, temp threshold-file factory, and a Redis-available patch helper (so US1 endpoint tests aren't 503'd by the Epic 1 gate)

**Checkpoint**: Engine skeleton importable; `detect("")` returns `[]`. User stories can begin.

---

## Phase 3: User Story 1 — Detect & inspect PII via the debug surface (Priority: P1) 🎯 MVP

**Goal**: `POST /v1/detect` returns entities (PERSON, LOCATION, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME) for Polish text, each with type/offsets/score/exact-text/metadata; empty input → `[]`; nothing substituted, stored, logged, or sent to an LLM.

**Independent Test**: Submit Polish text with a name, e-mail, phone, and date → entities returned with exact offsets (`text==input[start:end]`); empty input → `[]`; logs contain no PII (quickstart V1).

### Tests for User Story 1 ⚠️

- [ ] T012 [P] [US1] API tests for `POST /v1/detect` (entity shape; `text==input[start:end]`; empty input → `[]`; no input text/values in logs; **`detect()` makes no Redis/network I/O** — assert via patched Redis client / no outbound calls, FR-006) in `apps/gateway-api/tests/test_detect_api.py` (uses Redis-available patch from T011)
- [ ] T013 [P] [US1] Polish date recognizer tests (numeric `12.01.2024`/`12-01-2024`; worded `12 stycznia 2024 r.`; `kind` metadata) in `apps/gateway-api/tests/detection/test_date_pl.py`
- [ ] T014 [P] [US1] Engine detect/offset tests (PERSON/LOCATION/EMAIL/PHONE detected; offsets exact) in `apps/gateway-api/tests/detection/test_engine.py`

### Implementation for User Story 1

- [ ] T015 [P] [US1] `DateRecognizer` (numeric + worded genitive months + optional `r.`; `kind` metadata; context words `data`/`dnia`) in `apps/gateway-api/gateway_api/detection/recognizers/date_pl.py` (contracts/recognizers.md)
- [ ] T016 [US1] `build_registry()` configuring base recognizers — Email, `PhoneRecognizer(supported_regions=["PL"])` — and registering `DateRecognizer`, in `apps/gateway-api/gateway_api/detection/recognizers/__init__.py` (depends: T007, T015)
- [ ] T017 [US1] Wire `build_registry()` into `DetectionEngine`; finalize `RecognizerResult`→`DetectedEntity` mapping incl. metadata passthrough in `apps/gateway-api/gateway_api/detection/engine.py` (depends: T010, T016)
- [ ] T018 [US1] Thin `POST /v1/detect` router over `DetectionEngine.detect()`; empty/whitespace → `[]` in `apps/gateway-api/gateway_api/api/detect.py` (depends: T017; contracts/detect.openapi.yaml)
- [ ] T019 [US1] Register detect router in `apps/gateway-api/gateway_api/main.py`; add request logging of entity types/counts/scores/timings only — never text or values (Constitution VIII) (depends: T018)

**Checkpoint**: MVP — engine detects names/places/email/phone/dates end-to-end via the API.

---

## Phase 4: User Story 2 — Validated Polish identifiers & financial data with metadata (Priority: P2)

**Goal**: PESEL, NIP, REGON, bank account, and postal address detected with checksum-driven confidence and metadata (gender, REGON variant, IBAN/NRB format); bad-checksum values surfaced at low confidence, not dropped; separators normalized while offsets stay original.

**Independent Test**: Feed valid/invalid IDs (labelled/unlabelled, separated/unseparated) → all detected; valid scores > invalid; PESEL gender/birth-date and REGON variant correct; returned text matches original separated span (quickstart V2).

### Tests for User Story 2 ⚠️

- [ ] T020 [P] [US2] Pure checksum tests (PESEL control sum + gender + post-2000 date; NIP incl. leading-zero & `control==10` invalid; REGON-9; REGON-14; ISO-7064 mod-97) in `apps/gateway-api/tests/detection/test_checksums.py`
- [ ] T021 [P] [US2] PESEL recognizer tests (valid; bad-checksum kept at low score; separators; post-2000; labelled vs unlabelled) in `apps/gateway-api/tests/detection/test_pesel.py`
- [ ] T022 [P] [US2] NIP recognizer tests (valid; leading-zero accepted; bad-checksum kept; separators) in `apps/gateway-api/tests/detection/test_nip.py`
- [ ] T023 [P] [US2] REGON recognizer tests (9 vs 14 variant metadata; bad-checksum kept) in `apps/gateway-api/tests/detection/test_regon.py`
- [ ] T024 [P] [US2] Bank account tests (PL-prefixed IBAN vs continuous NRB; mod-97; low confidence in non-banking context) in `apps/gateway-api/tests/detection/test_bank_account.py`
- [ ] T025 [P] [US2] Address tests (with/without street; multi-line; `ul. Kowalskiego` stays address; postal code) in `apps/gateway-api/tests/detection/test_address.py`

### Implementation for User Story 2

- [ ] T026 [P] [US2] Pure checksum/derivation functions (PESEL ctrl+gender+birth-date/century; NIP; REGON-9; REGON-14; mod-97) in `apps/gateway-api/gateway_api/detection/checksums.py` (research "checksum algorithms")
- [ ] T027 [US2] `ChecksumPatternRecognizer` base — explicit valid/invalid **score bands** (keep invalid, do NOT drop), metadata via `recognition_metadata` — in `apps/gateway-api/gateway_api/detection/recognizers/_checksum_base.py` (depends: T005, T006, T026; research D3)
- [ ] T028 [P] [US2] `PeselRecognizer` (11-digit regex+separators; gender/birth_date/checksum_valid/normalized metadata; context `PESEL`) in `apps/gateway-api/gateway_api/detection/recognizers/pesel.py` (depends: T027)
- [ ] T029 [P] [US2] `NipRecognizer` in `apps/gateway-api/gateway_api/detection/recognizers/nip.py` (depends: T027)
- [ ] T030 [P] [US2] `RegonRecognizer` (9 & 14; `variant` metadata) in `apps/gateway-api/gateway_api/detection/recognizers/regon.py` (depends: T027)
- [ ] T031 [P] [US2] `PolishBankAccountRecognizer` (NRB/IBAN; `format`/`mod97_valid` metadata; context `nr rachunku`/`IBAN`) in `apps/gateway-api/gateway_api/detection/recognizers/bank_account.py` (depends: T027)
- [ ] T032 [P] [US2] `PolishAddressRecognizer` (street+building/flat+`XX-XXX`+city, multi-line; street-less variant; `has_street`/`postal_code` metadata) in `apps/gateway-api/gateway_api/detection/recognizers/address.py` (depends: T006)
- [ ] T033 [US2] Register the five custom recognizers in `build_registry()` in `apps/gateway-api/gateway_api/detection/recognizers/__init__.py` (depends: T028, T029, T030, T031, T032)

**Checkpoint**: All ten entity types detected; identifiers validated with metadata.

---

## Phase 5: User Story 3 — Explainable, configurable, recall-first scoring & thresholds (Priority: P3)

**Goal**: Deterministic score bands (base → checksum → +context bonus → clamp), per-type configurable thresholds with live reload, recall-first defaults, paranoid(0)/disable(1) extremes.

**Independent Test**: Same input twice → identical scores; labelled > unlabelled; threshold 0 surfaces all, 1 disables a type; threshold edit applies on next request without restart (quickstart V3).

### Tests for User Story 3 ⚠️

- [ ] T034 [P] [US3] Scoring-band tests (valid/invalid × labelled/unlabelled; clamp ≤0.99; determinism repeat-run) in `apps/gateway-api/tests/detection/test_scoring.py`
- [ ] T035 [P] [US3] Threshold tests (per-type post-filter; paranoid `0`=all; disable `1`=none; mtime live-reload without restart) in `apps/gateway-api/tests/detection/test_thresholds.py`

### Implementation for User Story 3

- [ ] T036 [US3] Wire `LemmaContextAwareEnhancer(context_similarity_factor=0.20, min_score_with_context_similarity=0.0)` into the `AnalyzerEngine`; ensure each recognizer's context words feed it in `apps/gateway-api/gateway_api/detection/engine.py` (depends: T017; research D6)
- [ ] T037 [US3] Apply the explicit band rules + clamp uniformly to base and custom results; document the band table in module docstring — **including the actual fixed default scores Presidio assigns to EMAIL_ADDRESS and PHONE_NUMBER** so every band is explicit (FR-015/FR-016) — in `apps/gateway-api/gateway_api/detection/scoring.py` (depends: T005)
- [ ] T038 [US3] Harden threshold post-filter: per-type + `default` fallback, `0`/`1` extremes, out-of-range clamp, missing-file fallback to shipped defaults in `apps/gateway-api/gateway_api/detection/thresholds.py` (depends: T008)

**Checkpoint**: Scoring is explainable and deterministic; thresholds tune recall without restart.

---

## Phase 6: User Story 4 — Resolve overlapping detections into one best entity (Priority: P3)

**Goal**: Deterministic "longest/containing span wins" pass; near-duplicates merged; ADDRESS subsumes contained LOCATION; `ul. Kowalskiego` not a separate PERSON; adjacent first+last names allowed as one or two spans.

**Independent Test**: REGON-9⊂REGON-14 → single 14-digit entity; city⊂address → no separate LOCATION; NIP⊂PESEL → PESEL (quickstart V4).

### Tests for User Story 4 ⚠️

- [ ] T039 [P] [US4] Overlap tests (NIP⊂PESEL→PESEL; REGON-9⊂REGON-14→14; city⊂address→no LOCATION; `ul. Kowalskiego` not PERSON; adjacent names kept) in `apps/gateway-api/tests/detection/test_overlap.py`

### Implementation for User Story 4

- [ ] T040 [US4] Deterministic overlap-resolution pass (sort by span length desc then start; drop fully-contained; merge near-duplicates — **including same-type `DATE_TIME` duplicates from the spaCy `date` label and the custom `DateRecognizer`**) in `apps/gateway-api/gateway_api/detection/engine.py` (depends: T017; research D4)
- [ ] T041 [US4] ADDRESS-subsumes-contained-LOCATION rule within the overlap pass in `apps/gateway-api/gateway_api/detection/engine.py` (depends: T040; FR-024/FR-025)

**Checkpoint**: Output is a single best entity per region; no contained duplicates.

---

## Phase 7: User Story 5 — Reflect language-model readiness in the health surface (Priority: P3)

**Goal**: `/health` `spacy_model` reports real readiness (degraded when not loaded); `POST /v1/detect` returns 503 when the model is not ready (no partial results); detect is exempt from the Redis gate.

**Independent Test**: model loaded → `spacy_model: ok`; not loaded → `unavailable` + overall `degraded` (still HTTP 200); detect 503 when model down; detect still served when Redis down (quickstart V5).

### Tests for User Story 5 ⚠️

- [ ] T042 [P] [US5] Health tests: `spacy_model` `ok` when ready / `unavailable`+`degraded` when not, `/health` still 200 in `apps/gateway-api/tests/test_health.py`
- [ ] T043 [P] [US5] Gating tests: `/v1/detect` 503 when model not ready (FR-030); served (200) when Redis down (FR-031) in `apps/gateway-api/tests/test_detect_gating.py`

### Implementation for User Story 5

- [ ] T044 [US5] Lifespan eager **background** model load at startup (worker thread; set ready flag on success, leave false + log on failure; never crash) in `apps/gateway-api/gateway_api/main.py` (depends: T007; research D8)
- [ ] T045 [US5] Replace Epic 1 stub: `check_spacy_model()` → `is_model_ready()` (`ok`/`unavailable`) in `apps/gateway-api/gateway_api/health.py` (depends: T007; contracts/health-readiness.md)
- [ ] T046 [US5] Model-readiness 503 dependency on `POST /v1/detect` (FR-030) in `apps/gateway-api/gateway_api/api/detect.py` (depends: T018, T007)
- [ ] T047 [US5] Exempt `/v1/detect` from the Redis-availability gate (add to the `/health` exemption) in `apps/gateway-api/gateway_api/main.py` (depends: T019; FR-031)

**Checkpoint**: Readiness honestly reported; detect gated on the model, not on Redis.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T048 [P] Document Constitution-IX limitations (worded-date gaps; `pl_core_news_lg` rare/foreign/inflected-name weakness; intentional over-detection) in `apps/gateway-api/README.md`
- [ ] T049 Audit all detection log statements (engine, route, lifespan) for no-PII compliance — only types/counts/scores/timings (Constitution VIII) across `gateway_api/detection/engine.py`, `gateway_api/api/detect.py`, `gateway_api/main.py`
- [ ] T050 Run the quickstart validation scenarios V1–V6 in `specs/002-pii-detection-engine/quickstart.md` against a running backend
- [ ] T051 [P] Lint + format: `nx run gateway-api:lint` and `nx run gateway-api:format`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks all stories**.
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US2 (Phase 4)**: depends on Foundational; recognizers/checksums independently unit-testable; surfaced through the engine once registered (T033).
- **US3 (Phase 5)**: depends on the engine from US1 (T017) — context enhancer + band finalization + threshold hardening.
- **US4 (Phase 6)**: depends on the engine from US1 (T017) — overlap pass.
- **US5 (Phase 7)**: depends on `nlp.py` (T007) + the endpoint (T018/T019).
- **Polish (Phase 8)**: depends on all targeted stories.

### User Story Dependencies

- US1 → independent (the MVP). US2 → independent (custom recognizers + checksums). US3, US4 → extend the shared `engine.py` (build on US1's engine wiring; each independently testable). US5 → wires health/gating around the endpoint. US3/US4/US5 do not depend on each other.

### Within Each Story

- Tests first (write, see fail), then models/helpers → recognizers → engine wiring → route. Custom recognizers (US2) depend on `_checksum_base.py` (T027) and `checksums.py` (T026).

### ⚠️ Same-file serialization (not parallel despite different stories)

`engine.py` is touched by T010 (found.), T017 (US1), T036 (US3), T040/T041 (US4) — run these **sequentially**. `main.py` by T019 (US1), T044 + T047 (US5). `recognizers/__init__.py` by T016 (US1) + T033 (US2). `scoring.py` by T005 + T037. `thresholds.py` by T008 + T038.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004, T005, T006, T007, T009 in parallel (T008 then T010 after their inputs).
- US1 tests T012–T014 in parallel; T015 in parallel with tests.
- US2: all test tasks T020–T025 in parallel; recognizer impls T028–T032 in parallel after T027.
- US3 tests T034–T035; US4 test T039; US5 tests T042–T043 — parallel within their phase.

---

## Parallel Example: User Story 2 (recognizers)

```bash
# Tests first (all independent files):
Task: "PESEL recognizer tests in tests/detection/test_pesel.py"
Task: "NIP recognizer tests in tests/detection/test_nip.py"
Task: "REGON recognizer tests in tests/detection/test_regon.py"
Task: "Bank account tests in tests/detection/test_bank_account.py"
Task: "Address tests in tests/detection/test_address.py"

# After T026 (checksums) + T027 (_checksum_base), implement recognizers in parallel:
Task: "PeselRecognizer in gateway_api/detection/recognizers/pesel.py"
Task: "NipRecognizer in gateway_api/detection/recognizers/nip.py"
Task: "RegonRecognizer in gateway_api/detection/recognizers/regon.py"
Task: "PolishBankAccountRecognizer in gateway_api/detection/recognizers/bank_account.py"
Task: "PolishAddressRecognizer in gateway_api/detection/recognizers/address.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** (quickstart V1: detect names/places/email/phone/dates via `POST /v1/detect`). Demoable engine.

### Incremental Delivery

1. Setup + Foundational → engine skeleton.
2. + US1 → MVP (free-text PII via API).
3. + US2 → validated Polish identifiers + metadata (the thesis-distinctive layer).
4. + US3 → explainable, tunable, recall-first scoring.
5. + US4 → clean, deduplicated output.
6. + US5 → honest readiness + correct gating.
7. Polish → limitations doc, log audit, quickstart run, lint.

### Notes

- `[P]` = different files, no incomplete dependency. Heed the same-file serialization list above.
- Recognizer/checksum unit tests need **no model**; engine/API tests need `pl_core_news_lg` (skip-if-absent; baked into the image, `uv run python -m spacy download pl_core_news_lg` for native dev).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- Never log input text or matched values (Constitution VIII) — enforced in T019/T049 and asserted in T012.
