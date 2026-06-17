# Implementation Plan: Code Readability Refactor — Naming & Module Decomposition

**Branch**: `im/04-refactor-structure-and-naming-convention` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-code-readability-refactor/spec.md`

## Summary

A behavior-preserving readability refactor of the `apps/gateway-api` backend, driven by three
review findings: (1) generic file names in `pseudonym_vault/` (`encryption.py`, `matching.py`,
`store.py`, `keys.py`, `session.py`) that don't reveal their role; (2) abbreviated identifiers
across the whole `gateway_api` package that force the reader to decode intent; and (3) the oversized
`pseudonym_vault/store.py` (362 lines, `MappingStore` ≈20 methods) that bundles ≥5 responsibilities.

Technical approach: rename the five vault modules to role-revealing names (keeping the contractual
class names `MappingStore`/`Encryptor`); decompose `store.py` **by domain responsibility** into a
thin `MappingStore` facade plus focused collaborators (encrypted-JSON codec, Redis session
repository, coreference resolver, unique-fake factory, original-surface restorer); expand
abbreviated identifiers to full intention-revealing names package-by-package; and capture the
conventions as an **auto-loaded agent rule** in `.claude/rules/`. The existing test suite and the
Redis/encryption wire formats are the regression contract — they do not change.

This plan analyzes and refines a user-supplied draft plan. Two corrections were verified against the
code and are folded in: the import blast radius is **8 files, not 7** (the draft missed
`tests/pseudonym_vault/test_matching.py`), and the agent rule lives in **`.claude/rules/`** per spec
FR-005 (Q1), **not** `docs/naming-conventions.md` as the draft proposed — because `.claude/rules/*.md`
is auto-loaded into agent context (confirmed against the official Claude Code memory docs).

## Technical Context

**Language/Version**: Python 3.12 (`requires-python = ">=3.12,<4"`)

**Primary Dependencies**: FastAPI, async `redis`, `cryptography` (AES-256-GCM), `faker` (`pl_PL`),
`spacy` / `presidio-analyzer`; dev: `ruff`, `pytest` (+ `pytest-asyncio`, `pytest-cov`), `fakeredis`.

**Storage**: Redis 7 — one HASH per session (`session:{id}`), field layout unchanged by this refactor.

**Testing**: `pytest` (`asyncio_mode = auto`), in-memory `fakeredis`; existing suite under
`apps/gateway-api/tests/` is the behavior oracle. Lint/format via `ruff` (line-length 88; rules
E/F/UP/B/SIM/I — note: pep8-naming `N` is **not** enabled, so the naming convention is review-enforced).

**Target Platform**: Linux container (Docker Compose), served by uvicorn.

**Project Type**: Web service (backend in an Nx integrated monorepo); only `apps/gateway-api` is in scope.

**Performance Goals**: N/A — pure refactor, no runtime behavior or performance change intended.

**Constraints**: No behavior change; all pre-existing tests must pass with **no assertion edits**
(only import paths / module file names update). Redis field layout, AES-256-GCM envelope, and HMAC
forward-field naming stay byte-compatible (no migration; pre-refactor sessions remain readable).
Public surface frozen: `MappingStore` constructor + method signatures, `Encryptor`,
`get_mapping_store`, and the three `/v1/...` routes. See [contracts/preserved-interfaces.md](contracts/preserved-interfaces.md).

**Scale/Scope**: `gateway_api/` ≈2,400 LOC across 41 files. File renames: 5 vault modules (+ their
test files). Module decomposition: 1 file → 6 cohesive units. Identifier cleanup: whole `gateway_api`
package, deepest in the vault. One new doc: `.claude/rules/python-naming-conventions.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

A naming/structure refactor touches code organization, not behavior — so most principles are
unaffected. The ones that could be endangered, and how the plan protects them:

| Principle | Impact | Verdict |
|---|---|---|
| I. Privacy by Design | Pipeline path unchanged; no passthrough introduced. | ✅ Pass |
| III. Reversibility + encryption scope | `EncryptedJsonCodec` wraps the **same** `Encryptor`; AES-256-GCM envelope, HMAC forward fields, and REV/FORMS/META layout are byte-identical. Originals stay encrypted; fakes/HMAC stay clear. | ✅ Pass (asserted by `test_encrypted_at_rest_*`) |
| VIII. No PII in Logs | No log statements change; field-name/value secrecy test retained. | ✅ Pass |
| IX. Simplicity over Completeness | Each new module maps to a concept already present in spec/data-model (codec, repository, coreference, collision-free minting, restoration); no speculative abstraction; every unit targets <~120 lines. | ✅ Pass |
| Technology Constraints | No stack/dependency change. | ✅ Pass |
| II, IV, V, VI, VII | Detection thresholds, provider adapters, sync mode, Polish-first recognizers, Faker realism — none touched. | ✅ Pass |

**Result: PASS — no violations.** The `SessionMappingRepository` extraction is not a constitutional
deviation; it *serves* Principle IX by isolating the Redis field-schema knowledge currently smeared
across ~10 methods. No `# CONSTITUTION EXCEPTION` needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-code-readability-refactor/
├── plan.md              # This file
├── research.md          # Phase 0: rename map, decomposition boundaries, rule location/enforcement
├── data-model.md        # Phase 1: module responsibility model + identifier rename catalog
├── quickstart.md        # Phase 1: validation guide (lint, tests, grep, round-trip)
├── contracts/
│   └── preserved-interfaces.md   # The frozen public/wire surface (regression contract)
└── checklists/
    └── requirements.md  # From /speckit-specify (all items pass)
```

### Source Code (repository root) — `pseudonym_vault/` before → after

```text
apps/gateway-api/gateway_api/pseudonym_vault/        # BEFORE (455 LOC)
├── __init__.py            (7)   from .store import MappingStore, get_mapping_store
├── encryption.py          (35)  Encryptor, key_from_settings
├── session.py             (26)  FWD/REV/FORMS/META, session_hash_key, SessionMeta
├── keys.py                (37)  mapping_key, fwd_field
├── matching.py            (56)  lemma_overlap, aligned_fake, bounded_levenshtein
└── store.py               (362) MappingStore (≈20 methods) + get_mapping_store

apps/gateway-api/gateway_api/pseudonym_vault/        # AFTER
├── __init__.py                  from .mapping_store import MappingStore, get_mapping_store
├── aes_gcm_encryption.py        Encryptor, key_from_settings, + EncryptedJsonCodec   (was encryption.py)
├── session_layout.py            FWD/REV/FORMS/META, session_hash_key, SessionMeta    (was session.py)
├── mapping_keys.py              mapping_key, fwd_field                               (was keys.py)
├── coreference_matching.py      lemma_overlap, aligned_fake, bounded_levenshtein,
│                                + CoreferenceResolver                                (was matching.py)
├── session_mapping_repository.py  SessionMappingRepository (Redis HASH owner)        (NEW)
├── unique_fake_factory.py       UniqueFakeFactory (collision-free minting)           (NEW)
├── original_restoration.py      OriginalSurfaceRestorer (case-aware restore)         (NEW)
└── mapping_store.py             MappingStore facade (thin orchestration) + get_mapping_store  (was store.py)
```

Import-update sites — **8 files**: 7 reference-update sites (`pseudonym_vault/__init__.py`,
`api/pseudonymize.py`, `tests/conftest.py`, and `tests/pseudonym_vault/{test_encryption,test_keys,test_matching,test_store}.py`)
plus `mapping_store.py`'s own internal imports (handled by T004). The matching test file
(`test_matching.py`) is the correction over the draft's count.

Identifier cleanup also runs (lighter touch, no file renames) across `pii_detection/`,
`pseudonym_generation/`, `api/`, and the top-level modules, per the agent rule.

**Structure Decision**: Keep the package boundary `gateway_api/pseudonym_vault/`. Split `store.py`
by responsibility into one facade + five collaborators (two of which absorb already-existing pure
modules). Public class names and signatures are frozen; only file names and internal organization
change. The full method→module mapping is in [data-model.md](data-model.md).

## Complexity Tracking

> No constitutional violations — table left intentionally minimal.

| Decision | Why it is not over-engineering |
|---|---|
| New `SessionMappingRepository` (repository pattern) | The Redis field-schema knowledge (prefixes FWD/REV/FORMS/META, encrypt/decrypt at each boundary) is currently duplicated across ~10 `MappingStore` methods. One owner removes that duplication and is the single seam protecting Constitution III/VIII. Direct `redis` calls scattered in the facade were the rejected (status-quo) alternative. |
| 6 modules from 1 | Each maps to a named concept already in the spec/data-model; the alternative (a single 362-line class) is exactly the reviewed defect. |

## Phase outputs

- **Phase 0 — [research.md](research.md)**: file-rename decisions + rationale, the by-domain
  decomposition analysis (method → responsibility → target module), agent-rule location
  (`.claude/rules/` vs `docs/` — resolved to `.claude/rules/`), and enforcement approach
  (review-based; pep8-naming not enabled).
- **Phase 1 — [data-model.md](data-model.md)**: post-refactor module responsibility model, the
  `store.py` method migration map, and the identifier rename catalog (verified against the code).
- **Phase 1 — [contracts/preserved-interfaces.md](contracts/preserved-interfaces.md)**: the frozen
  public API + Redis/encryption wire formats that the refactor must not change.
- **Phase 1 — [quickstart.md](quickstart.md)**: how to validate the refactor (ruff, full pytest,
  leftover-abbreviation grep, `/memory` rule-load check, end-to-end round-trip).
- **Phase 1 — agent context**: CLAUDE.md SPECKIT section updated to point at this plan.
