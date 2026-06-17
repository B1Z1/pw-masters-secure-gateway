---
description: "Task list for Code Readability Refactor — Naming & Module Decomposition"
---

# Tasks: Code Readability Refactor — Naming & Module Decomposition

**Input**: Design documents from `specs/004-code-readability-refactor/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/preserved-interfaces.md](contracts/preserved-interfaces.md),
[quickstart.md](quickstart.md)

**Tests**: NOT requested. This is a behavior-preserving refactor — the **existing** suite under
`apps/gateway-api/tests/` is the regression oracle (FR-006, SC-003). No new test-authoring tasks; each
story ends with a verification task that runs the existing tests + lint + grep. No assertion edits are
permitted — only import paths and renamed test files change.

**Organization**: Tasks grouped by user story. All paths are relative to repo root
`/Users/illia-personal/Projects/pw-masters-secure-gateway`. Backend root: `apps/gateway-api/`,
package: `apps/gateway-api/gateway_api/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Toolchain ready for a refactor with a trustworthy before/after comparison.

- [ ] T001 Sync backend deps and confirm Python 3.12 toolchain: `cd apps/gateway-api && uv sync` (verify `uv run python -V` is 3.12).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Capture the green baseline that every story is measured against. Without it, "no
regression" is unprovable.

**⚠️ CRITICAL**: No user story work begins until the baseline is recorded.

- [ ] T002 Record the green baseline in `apps/gateway-api`: run `uv run ruff check gateway_api tests`, `uv run ruff format --check gateway_api tests`, and `uv run pytest tests/`; note the exact pass/skip/deselect counts (this is the reference for T009/T017/T024/T027). Confirm a clean tree before starting (`git status`).

**Checkpoint**: Baseline captured — user stories can begin.

---

## Phase 3: User Story 1 - Descriptive module/file names (Priority: P1) 🎯 MVP

**Goal**: Every `pseudonym_vault/` file name reveals its role; the app and tests import and pass.
Public class names (`MappingStore`, `Encryptor`) are unchanged — only file names and imports move.

**Independent Test**: `uv run python -c "import gateway_api.main"` succeeds; `uv run pytest tests/`
matches the T002 baseline; grep finds no stale `pseudonym_vault.(store|encryption|matching|keys|session)`
references (quickstart §3).

### Implementation for User Story 1

- [ ] T003 [US1] `git mv` the 5 source modules in `apps/gateway-api/gateway_api/pseudonym_vault/`: `store.py`→`mapping_store.py`, `encryption.py`→`aes_gcm_encryption.py`, `matching.py`→`coreference_matching.py`, `keys.py`→`mapping_keys.py`, `session.py`→`session_layout.py` (preserves history; do as one coordinated step — the modules import each other).
- [ ] T004 [US1] Fix the intra-package imports at the top of `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py` (currently lines 18–21): `.encryption`→`.aes_gcm_encryption`, `.keys`→`.mapping_keys`, `.matching`→`.coreference_matching`, `.session`→`.session_layout`.
- [ ] T005 [P] [US1] Update `apps/gateway-api/gateway_api/pseudonym_vault/__init__.py`: `from .store import MappingStore, get_mapping_store` → `from .mapping_store import ...`.
- [ ] T006 [P] [US1] Update `apps/gateway-api/gateway_api/api/pseudonymize.py` (line 20): `from ..pseudonym_vault.store import get_mapping_store` → `from ..pseudonym_vault.mapping_store import get_mapping_store`.
- [ ] T007 [US1] `git mv` the test files in `apps/gateway-api/tests/pseudonym_vault/` for naming consistency: `test_encryption.py`→`test_aes_gcm_encryption.py`, `test_keys.py`→`test_mapping_keys.py`, `test_matching.py`→`test_coreference_matching.py`, `test_store.py`→`test_mapping_store.py`.
- [ ] T008 [US1] Update test imports (no assertion changes): `apps/gateway-api/tests/conftest.py` (lines 111–112: `encryption`→`aes_gcm_encryption`, `store`→`mapping_store`); `test_aes_gcm_encryption.py` (line 7); `test_mapping_keys.py` (line 5: `keys`→`mapping_keys`); `test_coreference_matching.py` (line 5: `matching`→`coreference_matching`); `test_mapping_store.py` (lines 6–7: `encryption`→`aes_gcm_encryption`, `store`→`mapping_store`).
- [ ] T009 [US1] **Verify US1**: in `apps/gateway-api` run `uv run ruff check gateway_api tests`, `uv run pytest tests/` (matches T002 baseline), and the quickstart §3 grep (no stale module references; old filenames gone; `import gateway_api.main` works).

**Checkpoint**: Vault files are role-named; behavior unchanged. Shippable MVP increment.

---

## Phase 4: User Story 2 - Full identifiers + agent rule (Priority: P2)

**Goal**: No abbreviated/cryptic identifiers (per the acronym allowlist) remain across `gateway_api`;
the naming convention is captured as an auto-loaded agent rule.

**Independent Test**: quickstart §4 grep finds none of the listed abbreviations in refactored
modules; `uv run ruff check` clean and `uv run pytest tests/` matches baseline; `/memory` lists
`python-naming-conventions.md` (quickstart §6).

> Scope note: T013 cleans identifiers in `mapping_store.py` **in place** (locals/attributes only —
> `_seal`/`_open` stay until US3 moves them into the codec). US3 later relocates this already-clean
> code into collaborators, so the two stories touch the file sequentially, never in conflict.

### Implementation for User Story 2

- [ ] T010 [US2] Create `.claude/rules/python-naming-conventions.md` with YAML frontmatter `paths: ["apps/gateway-api/**/*.py"]`; content per [data-model.md](data-model.md) §4 (file/module rules incl. forbidden generic names; full-identifier rules; loop-variable rules; boolean `is_/has_/should_`; constant `UPPER_SNAKE`; acronym handling) and a before/after table sourced from data-model §3.
- [ ] T011 [P] [US2] Apply the identifier renames in `apps/gateway-api/gateway_api/pseudonym_vault/coreference_matching.py` per data-model §3 (`cset/sset`→`candidate_tokens/stored_tokens`, `cs/ss`→`candidate_set/stored_set`, `a/b`→`source/target`, `ca/cb`→`source_char/target_char`, `cur/prev`→`current_row/previous_row`, `val`→`edit_distance`, `idxs`→`matched_indices`, `picked`→`aligned_tokens`, `i/j`→`source_index/target_index`, `max_dist`→`max_distance`).
- [ ] T012 [P] [US2] Apply identifier renames in `apps/gateway-api/gateway_api/pseudonym_vault/mapping_keys.py` (`mkey`→`normalized_key`, `mac`→`hmac_digest`) and `aes_gcm_encryption.py` (`_aes`→`_cipher`, `blob`→`encrypted_envelope`).
- [ ] T013 [US2] Apply identifier renames in `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py` per data-model §3 (`hkey`→`session_key`, `mkey`→`normalized_key`, `fwd`→`forward_field_name`, `_gen`→`_generator`, `_key`→`_encryption_key`, `_ttl`→`_session_ttl_seconds`, `cached`→`cached_forward_value`, `ob`→`original_base`, `rec`→`reverse_record`, `d/best_d`→`distance/best_distance`, `blob`→`encrypted_value`, `fmap`→`forms_by_case`, loop vars `c/m/f/t/w`, `is_name`→`is_inflecting_name`) — leave `_seal`/`_open` for US3.
- [ ] T014 [P] [US2] Apply the naming rule across `apps/gateway-api/gateway_api/pii_detection/` (expand single-letter loop vars and local abbreviations in `engine.py`, `scoring.py`, `nlp.py`, `normalization.py`, `recognizers/*`); keep conventional filenames `dto.py`/`nlp.py` (documented allowance).
- [ ] T015 [P] [US2] Apply the naming rule across `apps/gateway-api/gateway_api/pseudonym_generation/` (`generator.py`, `inflection.py`, `builders/*`, `dto.py`).
- [ ] T016 [P] [US2] Apply the naming rule across `apps/gateway-api/gateway_api/api/` (`detect.py`, `pseudonymize.py`) and the top-level modules (`config.py`, `dependencies.py`, `health.py`, `main.py`).
- [ ] T017 [US2] **Verify US2**: `uv run ruff check gateway_api tests` clean; `uv run pytest tests/` matches baseline; quickstart §4 grep clean across the **whole `gateway_api/` package** (all packages — `pseudonym_vault/`, `pii_detection/`, `pseudonym_generation/`, `api/`, top-level — not just the vault); open a backend `.py` in Claude Code and confirm `/memory` lists `python-naming-conventions.md`.

**Checkpoint**: Code is self-documenting per the rule; the rule auto-loads for future agents.

---

## Phase 5: User Story 3 - Decompose mapping_store.py by responsibility (Priority: P3)

**Goal**: Split the (renamed, clean) `mapping_store.py` into a thin `MappingStore` facade plus five
single-responsibility collaborators; public signatures and wire formats frozen.

**Independent Test**: the 8 vault `.py` files exist (6 logic units + `__init__` + `session_layout`),
`mapping_store.py` ≤ ~150 lines of orchestration, `uv run pytest tests/pseudonym_vault/ -v` green
(coreference, fuzzy restore, collision-free, at-rest secrecy, TTL, listing), full suite matches
baseline. Constructor `MappingStore(redis, encryptor, key_bytes, ttl, generator)` unchanged.

> Depends on US1 (file already named `mapping_store.py`) and benefits from US2 (clean identifiers to
> relocate). See [contracts/preserved-interfaces.md](contracts/preserved-interfaces.md) for the frozen surface.

### Implementation for User Story 3

- [ ] T018 [P] [US3] Add `EncryptedJsonCodec` (`encrypt_object`/`decrypt_object` over `Encryptor`) to `apps/gateway-api/gateway_api/pseudonym_vault/aes_gcm_encryption.py`, migrating the `_seal`/`_open` logic out of `mapping_store.py`. Pure (no Redis).
- [ ] T019 [P] [US3] Add `CoreferenceResolver.resolve(entity, normalized_key, coref_records) -> str | None` to `apps/gateway-api/gateway_api/pseudonym_vault/coreference_matching.py`, extracting the 0/1/≥2 decision + `aligned_fake` from `_try_coreference`. Pure — Redis loading stays in the facade.
- [ ] T020 [P] [US3] Create `apps/gateway-api/gateway_api/pseudonym_vault/unique_fake_factory.py` with `UniqueFakeFactory(generator).mint(entity, used_forms) -> FakeValue`, moving the `_generate_and_store` retry loop + `_force_unique` deterministic fallback (research D6). Pure w.r.t. Redis.
- [ ] T021 [P] [US3] Create `apps/gateway-api/gateway_api/pseudonym_vault/original_restoration.py` with `OriginalSurfaceRestorer` (`restore_surface(record)`, `render_case(forms, case)`, `titlecase(lemma)`), moving `_restore_surface`/`_render`/`_titlecase`. Pure (inflection only).
- [ ] T022 [US3] Create `apps/gateway-api/gateway_api/pseudonym_vault/session_mapping_repository.py` with `SessionMappingRepository` — the sole owner of `redis`, the `EncryptedJsonCodec`, the HMAC key, and the `FWD/REV/FORMS/META` prefixes. Methods: `read_forward`, `write_mapping`, `write_exact_reverse`, `iter_reverse_records`, `used_fake_forms`, `load_corefs`, `append_coref`, `bump_meta`, `extend_ttl`, `delete`. Move all `hget/hgetall/hset` + `_used_fakes`/`_load_corefs`/`_write_mapping`/`_bump_meta` + the inline exact-REV write here; remove the `hkey.split(":", 1)[1]` hack (repo owns `session_id`). Keeps the Redis field layout byte-identical.
- [ ] T023 [US3] Rewrite `apps/gateway-api/gateway_api/pseudonym_vault/mapping_store.py` as a thin `MappingStore` facade: keep the constructor `(redis, encryptor, key_bytes, ttl, generator)` and all public method signatures (`get_or_create`, `get_original`, `get_all_mappings`, `restore_text`, `delete_session`, `extend_ttl`) plus `get_mapping_store()`; compose codec/repository/resolver/factory/restorer and delegate; hoist the function-local `import re` and `from datetime import datetime` to module top.
- [ ] T024 [US3] **Verify US3**: `uv run pytest tests/pseudonym_vault/ -v` and full `uv run pytest tests/` match baseline; `uv run ruff check gateway_api tests` clean; confirm `mapping_store.py` ≤ ~150 lines and each new module maps to one responsibility (data-model §1).

**Checkpoint**: `store.py` is decomposed; the public/wire contract is intact.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final readability sweep and end-to-end confirmation.

- [ ] T025 [P] Remove comments that merely restate WHAT the code does; keep WHY/rationale comments (research refs, constitution notes) across all refactored modules (SC-005).
- [ ] T026 [P] End-to-end round-trip per quickstart §7 (requires Redis + `REDIS_ENCRYPTION_KEY`): `POST /v1/pseudonymize` then `POST /v1/depseudonymize` on a Polish-PII example from `specs/003-fake-data-generator/quickstart.md`; restored text equals original.
- [ ] T027 Final full verification against [contracts/preserved-interfaces.md](contracts/preserved-interfaces.md): `uv run ruff check` + `ruff format --check` + full `uv run pytest tests/` (baseline match); confirm routes, `MappingStore`/`Encryptor` signatures, Redis field layout, and AES-GCM envelope unchanged. Also sanity-check SC-007: a reader can locate a given vault concern (e.g. "where are originals restored?" → `original_restoration.py`) from file names alone in under a minute.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: after Setup — baseline BLOCKS all stories.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after US1 (operates on the renamed files).
- **US3 (Phase 5)**: after US1 (needs `mapping_store.py`); best after US2 (relocates already-clean code).
- **Polish (Phase 6)**: after US3.

### User Story Dependencies (refactor reality)

Unlike a greenfield feature, these stories share the vault files, so they run **sequentially**
(US1 → US2 → US3), which also matches priority order. This is intentional, not a contradiction:
file renames must land before identifier cleanup, which must land before decomposition relocates the
code. Each story is still **independently testable** at its checkpoint (the suite is green and the
specific goal is met) and could be shipped/demoed on its own.

### Within Each Story

- US1: T003 → T004 (same file just renamed) → then T005/T006 [P]; T007 → T008; → T009 verify.
- US2: T010 first (rule guides the rest) → T011/T012/T014/T015/T016 [P] (distinct files) + T013 → T017 verify.
- US3: T018/T019/T020/T021 [P] (distinct files) → T022 (repository) → T023 (facade composes all) → T024 verify.

### Parallel Opportunities

- US1: T005, T006.
- US2: T011, T012, T014, T015, T016 (all distinct files); T013 alongside them (distinct file).
- US3: T018, T019, T020, T021 (distinct files) before T022/T023.
- Polish: T025, T026.

---

## Parallel Example: User Story 3

```bash
# After US1/US2, launch the four pure-extraction tasks together (distinct files):
Task: "T018 Add EncryptedJsonCodec to pseudonym_vault/aes_gcm_encryption.py"
Task: "T019 Add CoreferenceResolver to pseudonym_vault/coreference_matching.py"
Task: "T020 Create pseudonym_vault/unique_fake_factory.py"
Task: "T021 Create pseudonym_vault/original_restoration.py"
# Then T022 (repository) and finally T023 (facade) which composes them all.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → 2. Phase 2 Foundational (baseline) → 3. Phase 3 US1 → 4. **STOP & VALIDATE**
(T009): files role-named, suite green. This alone resolves the user's primary "names tell me nothing"
complaint and is independently shippable.

### Incremental Delivery

US1 (role-named files) → US2 (self-documenting identifiers + auto-loaded agent rule) → US3
(decomposed `store.py`). Each ends green and adds value without breaking the previous.

---

## Notes

- Tests are NOT authored here — the existing suite is the oracle; only import paths and test-file
  names change, never assertions (FR-006, SC-003).
- Constitution III/VIII are guarded throughout by `test_encrypted_at_rest_no_pii_in_names_or_values`
  and the unchanged Redis/encryption formats — re-run it after US3.
- Commit after each task or logical group; keep `MappingStore`/`Encryptor` class names fixed.
- Total: 27 tasks (Setup 1, Foundational 1, US1 7, US2 8, US3 7, Polish 3).
