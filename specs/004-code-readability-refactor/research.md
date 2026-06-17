# Phase 0 Research — Code Readability Refactor

Decisions that resolve the open questions before design. Each: **Decision / Rationale /
Alternatives considered**. Grounded in the current code, the spec, the constitution, and a
verification pass over imports and tests.

---

## D1 — Vault file renames (role-revealing names)

**Decision**: Rename the five `pseudonym_vault/` modules; **keep the public class names**
(`MappingStore`, `Encryptor`) unchanged.

| Current file | New file | Why the new name |
|---|---|---|
| `store.py` | `mapping_store.py` | Mirrors the dominant class `MappingStore`. |
| `encryption.py` | `aes_gcm_encryption.py` | Names *which* scheme (AES-256-GCM), not just "encryption". |
| `matching.py` | `coreference_matching.py` | Dominant domain is coreference matching of names. |
| `keys.py` | `mapping_keys.py` | Mapping keys + HMAC forward field names. |
| `session.py` | `session_layout.py` | Redis HASH field layout + `SessionMeta`. |

**Rationale**: The spec (US1, FR-001) requires file names to reveal their responsibility. Class names
are frozen because they appear in the EPIC 3 contracts (`specs/003-fake-data-generator/contracts/mapping-store.md`,
`encryption.md`) and in test imports — renaming them is a large blast radius for no readability gain
the file rename doesn't already deliver.

**Alternatives considered**:
- Rename classes too (e.g. `MappingStore` → `SessionPseudonymStore`) — rejected: breaks the
  published contract and every test, violating the "no assertion edits" constraint.
- Leave files, rename only via docstrings — rejected: the file tree itself must document structure (SC-001).
- `session.py` → `redis_field_layout.py` — rejected as slightly leaky (couples the name to Redis);
  `session_layout.py` keeps the domain word while still signaling "layout/schema".

---

## D2 — Decompose `store.py` by responsibility (not by line count)

**Decision**: Split `MappingStore` into a **thin facade** plus five collaborators, each owning one
concept already present in the data-model. Target ≤~120 lines per unit.

| Responsibility | Today (in `store.py`) | Target module / type |
|---|---|---|
| Encrypted JSON (de)serialization | `_seal`, `_open` | `aes_gcm_encryption.py` → new `EncryptedJsonCodec` (`encrypt_object`/`decrypt_object`) over `Encryptor`. Pure (no Redis). |
| Redis HASH persistence (field schema) | `_used_fakes`, `_load_corefs`, `_write_mapping`, `_bump_meta`, `extend_ttl`, `delete_session`, the inline exact-REV write in `get_or_create`, and every raw `hget/hgetall/hset` | new `session_mapping_repository.py` → `SessionMappingRepository`: the **only** holder of `redis`, the codec, the HMAC key, and the FWD/REV/FORMS/META prefixes. |
| Coreference decision (reuse a name's fake) | decision part of `_try_coreference` | `coreference_matching.py` → new `CoreferenceResolver.resolve(...)` → `fake_base | None` (0/1/≥2 rule + `aligned_fake`). Pure; Redis load done by the facade. |
| Collision-free fake minting | `_generate_and_store` retry loop, `_force_unique` | new `unique_fake_factory.py` → `UniqueFakeFactory(generator).mint(entity, used_forms)` (research D6). Pure w.r.t. Redis. |
| Case-aware original restoration | `_render`, `_restore_surface`, `_titlecase` | new `original_restoration.py` → `OriginalSurfaceRestorer` (`restore_surface(record)`, `render_case(forms, case)`, `titlecase(lemma)`). Pure (inflection only). |
| Session API / orchestration | `get_or_create`, `get_original`, `get_all_mappings`, `restore_text`, `delete_session`, `extend_ttl`, `get_mapping_store` | `mapping_store.py` → `MappingStore` as thin orchestration delegating to the above. |

**Facade composition (signature frozen)**: `MappingStore(redis, encryptor, key_bytes, ttl, generator)`
stays positional (used by `conftest.make_store` and `test_collision_free`). Internally it builds:
`codec = EncryptedJsonCodec(encryptor)`; `repository = SessionMappingRepository(redis, codec, key_bytes, ttl)`;
`resolver = CoreferenceResolver()`; `factory = UniqueFakeFactory(generator)`;
`restorer = OriginalSurfaceRestorer()`. `key_bytes` is still needed independently of `encryptor`
because it keys the HMAC forward field (`fwd_field`), distinct from AES encryption.

**Rationale**: Directly answers US3/FR-004. Each module is independently understandable and testable;
the repository becomes the single audit point for Constitution III/VIII.

**Alternatives considered**:
- Mechanical split by line count — rejected by the user ("po domenach, nie po liczbie linii").
- Keep persistence inline in the facade, extract only pure helpers — rejected: leaves the
  field-schema duplication (the core readability problem) and weakens the III/VIII audit seam.
- One combined `vault_internals.py` grab-bag — rejected: just renames the god-object.

**Open nuance (noted, not blocking)**: `bounded_levenshtein` serves the *restore* fuzzy-match path,
not coreference, yet lives with the coreference primitives. It stays in `coreference_matching.py` as
a shared approximate-matching primitive (moving it would fragment a 3-function module); a one-line
docstring will clarify its dual use.

---

## D3 — Facade cleanups taken opportunistically

**Decision**: While building the facade, (a) drop the `hkey.split(":", 1)[1]` hack by having the
repository own `session_id`/key derivation, and (b) hoist the function-local imports
(`import re` in `restore_text`, `from datetime import datetime` in `_bump_meta`) to module top.

**Rationale**: Both are concrete readability smells in the reviewed file; fixing them is in-scope for
US1/US2 and risk-free. **Alternatives**: defer to a later pass — rejected; they're in the file we're
already rewriting.

---

## D4 — Identifier naming convention (whole `gateway_api`)

**Decision**: Full, intention-revealing identifiers; no abbreviations except domain acronyms
(PII, PESEL, NIP, REGON, NRB, HMAC, TTL, AES, GCM) and only where the acronym *is* the clearest word.
Applied across the whole package, deepest in the vault. The concrete rename catalog is in
[data-model.md](data-model.md) (e.g. `hkey`→`session_key`, `mkey`→`normalized_key`,
`fwd`→`forward_field_name`, `blob`→`encrypted_value`, `ob`→`original_base`, `rec`→`reverse_record`,
`cur/prev`→`current_row/previous_row`, single-letter loop vars → meaningful names).

**Rationale**: FR-002/FR-003 + Constitution IX (self-documenting code reduces the comment burden).

**Alternatives considered**:
- Enable ruff `pep8-naming` (`N`) to enforce automatically — rejected as insufficient: `N` checks
  *casing*, not *abbreviation/length*. It would not flag `hkey` or `d`. Convention stays
  review-enforced; enabling `N` could be a separate, additive follow-up but is not required here.
- Keep short locals inside tight algorithms (e.g. Levenshtein `i/j/cur/prev`) — rejected for this
  codebase: the user explicitly called these out, and the readability goal applies to algorithms too.

---

## D5 — Agent naming rule: location & format  ⚠ divergence from the draft plan

**Decision**: Author the rule as **`.claude/rules/python-naming-conventions.md`** with YAML
frontmatter `paths: ["apps/gateway-api/**/*.py"]`. **Not** `docs/naming-conventions.md`.

**Rationale**: Spec FR-005 (clarification Q1) and verification against the official Claude Code
memory docs (https://code.claude.com/docs/en/memory): every `.md` in `.claude/rules/` is
**auto-loaded into agent context** at session start with the same priority as `.claude/CLAUDE.md`;
adding `paths` frontmatter scopes loading to matching files, so the rule only costs context when an
agent edits backend Python. A file in `docs/` would **not** auto-load and would rely on a human
remembering to cite it — which defeats the user's stated goal ("rule dla agentów na przyszłość").
Loading is verifiable via `/memory`.

**Content** (mirrors the draft's Part D, retargeted): module-name rules (descriptive/domain;
forbid `utils`/`helpers`/`common`/`misc`/`store`/`encryption`/`matching`/`core`); identifier rules
(full words, no abbreviations, intent-revealing → no explanatory comments); loop-variable rules;
boolean (`is_/has_/should_`) and constant (`UPPER_SNAKE`) rules; acronym handling; and a
**before/after table built from this refactor's real renames** (from data-model.md) as the worked example.

**Alternatives considered**:
- `docs/naming-conventions.md` + a one-line pointer in `CLAUDE.md` (the draft) — rejected: not
  auto-loaded; `CLAUDE.md` import would load it unconditionally (more context, no path-scoping).
- A new principle in `constitution.md` — rejected: heavier governance than a code-style rule warrants,
  and the constitution is scoped to privacy/architecture, not lexical style.
- `~/.claude/rules/` (user-level) — rejected: machine-local, not shared via source control; the team
  (thesis reviewers) wouldn't get it.

---

## D6 — Regression safety net (verification strategy)

**Decision**: Treat the existing suite + wire formats as the contract. Verify with: `ruff check` +
`ruff format --check`; full `pytest` (the `pseudonym_vault/` tests cover coreference, fuzzy restore,
collision-free minting, at-rest secrecy, TTL, listing); a control `grep` for leftover abbreviations
in refactored modules; and an end-to-end `/v1/pseudonymize` → `/v1/depseudonymize` round-trip
(requires Redis; Epic 1 gate). Details in [quickstart.md](quickstart.md).

**Rationale**: The refactor's correctness claim *is* "tests still pass unedited" (FR-006, SC-003).
The at-rest test (`test_encrypted_at_rest_no_pii_in_names_or_values`) directly guards Constitution
III/VIII through the decomposition.

**Alternatives considered**: add new unit tests for each extracted collaborator — deferred to the
tasks phase as optional hardening; not required for the behavior-preservation guarantee and out of
scope for planning.
