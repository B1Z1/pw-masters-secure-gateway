# Phase 1 Data Model — Module & Naming Model

For a refactor, the "data model" is the **post-refactor structure**: which modules/types exist, what
each owns, how `store.py`'s methods migrate, and the verified identifier rename catalog. The data on
the wire (Redis fields, encryption envelope) does **not** change — see
[contracts/preserved-interfaces.md](contracts/preserved-interfaces.md).

---

## 1. Module responsibility model (`pseudonym_vault/` after)

| Module | Public type(s) | Responsibility | Depends on | Pure? | Est. LOC |
|---|---|---|---|---|---|
| `aes_gcm_encryption.py` | `Encryptor`, `EncryptedJsonCodec`, `key_from_settings` | AES-256-GCM encrypt/decrypt of bytes; JSON-object seal/open built on it | `cryptography` | yes | ~55 |
| `session_layout.py` | `SessionMeta`, `session_hash_key`, `FWD/REV/FORMS/META` | Redis HASH field prefixes + session metadata shape | — | yes | ~26 |
| `mapping_keys.py` | `mapping_key`, `fwd_field` | Normalized mapping key per type; HMAC forward field name | `hmac`, normalization | yes | ~37 |
| `coreference_matching.py` | `lemma_overlap`, `aligned_fake`, `bounded_levenshtein`, `CoreferenceResolver` | Name-coreference decision + approximate (fuzzy) matching primitives | — | yes | ~80 |
| `session_mapping_repository.py` (NEW) | `SessionMappingRepository` | Sole owner of `redis`, the codec, the HMAC key, and the field schema; all reads/writes/TTL | `redis`, codec, `session_layout`, `mapping_keys` | no (I/O) | ~110 |
| `unique_fake_factory.py` (NEW) | `UniqueFakeFactory` | Mint a fake guaranteed not to collide with used forms (retry + deterministic fallback) | `pseudonym_generation` | yes | ~45 |
| `original_restoration.py` (NEW) | `OriginalSurfaceRestorer` | Case-aware reconstruction of the original surface from a reverse record | `pseudonym_generation.inflection` | yes | ~45 |
| `mapping_store.py` | `MappingStore`, `get_mapping_store` | Thin orchestration of the above; the public session API | all of the above | no | ~120–150 |

**Collaboration (facade construction, frozen ctor)**

```text
MappingStore(redis, encryptor, key_bytes, ttl, generator)
  ├─ EncryptedJsonCodec(encryptor)                      # encrypt_object / decrypt_object
  ├─ SessionMappingRepository(redis, codec, key_bytes, ttl)
  ├─ CoreferenceResolver()
  ├─ UniqueFakeFactory(generator)
  └─ OriginalSurfaceRestorer()
```

---

## 2. `store.py` method → target migration map

| Current method (in `MappingStore`) | Destination | New form |
|---|---|---|
| `_seal`, `_open` | `EncryptedJsonCodec` | `encrypt_object(obj) -> bytes`, `decrypt_object(blob) -> Any` |
| `extend_ttl`, `delete_session` | `SessionMappingRepository` | `extend_ttl(session_id)`, `delete(session_id)` (facade keeps same-named public passthroughs) |
| `_used_fakes` | `SessionMappingRepository` | `used_fake_forms(session_id) -> set[str]` |
| `_load_corefs` + coref append in `_write_mapping` | `SessionMappingRepository` | `load_corefs(session_id)`, `append_coref(session_id, record)` |
| `_write_mapping` (persistence part) | `SessionMappingRepository` | `write_mapping(session_id, ...)`, `write_exact_reverse(session_id, ...)` |
| inline exact-REV write in `get_or_create` | `SessionMappingRepository` | `write_exact_reverse(...)` |
| reads in `get_original`/`restore_text`/`get_all_mappings` (raw `hgetall` + prefix filter) | `SessionMappingRepository` | `iter_reverse_records(session_id)`, `read_forward(session_id, field)` |
| `_bump_meta` | `SessionMappingRepository` | `bump_meta(session_id)` |
| `_try_coreference` (decision) | `CoreferenceResolver` | `resolve(entity, normalized_key, coref_records) -> str | None` |
| `_generate_and_store` (retry loop), `_force_unique` | `UniqueFakeFactory` | `mint(entity, used_forms) -> FakeValue` |
| `_render`, `_restore_surface`, `_titlecase` | `OriginalSurfaceRestorer` | `render_case(forms, case)`, `restore_surface(record)`, `titlecase(lemma)` |
| `get_or_create`, `get_original`, `get_all_mappings`, `restore_text`, `delete_session`, `extend_ttl` | `MappingStore` (facade) | **unchanged signatures**; bodies delegate |
| `get_mapping_store` (module fn) | `mapping_store.py` | unchanged |

The facade orchestrates: load corefs → `CoreferenceResolver.resolve` → on miss `UniqueFakeFactory.mint`
→ `SessionMappingRepository.write_*` → `extend_ttl`. Restore path: `iter_reverse_records` →
`OriginalSurfaceRestorer` → longest-first replace.

---

## 3. Identifier rename catalog (verified against current code)

Authoritative for the agent rule's before/after table. Vault is exhaustive; other packages follow
the same rule package-by-package.

### `mapping_store.py` (from `store.py`)

| Before | After |
|---|---|
| `hkey` | `session_key` (the `session:{id}` Redis key) |
| `mkey` | `normalized_key` |
| `fwd` | `forward_field_name` |
| `_enc` | (removed — via `EncryptedJsonCodec`) |
| `_gen` | `_generator` |
| `_key` | `_encryption_key` |
| `_ttl` | `_session_ttl_seconds` |
| `_seal` / `_open` | `encrypt_object` / `decrypt_object` (on codec) |
| `cached` | `cached_forward_value` |
| `ob` | `original_base` |
| `rec` | `reverse_record` |
| `d`, `best_d` | `distance`, `best_distance` |
| `blob`, `forms_blob` | `encrypted_value`, `encrypted_forms` |
| `fmap` | `forms_by_case` |
| `c` / `m` / `f` / `t` / `w` (loops) | `coref_record` / `match` / `form_field` / `token` / `word` |
| `is_name` | `is_inflecting_name` |

### `coreference_matching.py` (from `matching.py`)

| Before | After |
|---|---|
| `cset` / `sset` | `candidate_tokens` / `stored_tokens` |
| `cs` / `ss` | `candidate_set` / `stored_set` |
| `a` / `b` | `source` / `target` |
| `ca` / `cb` | `source_char` / `target_char` |
| `cur` / `prev` | `current_row` / `previous_row` |
| `val` | `edit_distance` |
| `idxs` | `matched_indices` |
| `picked` | `aligned_tokens` |
| `i` / `j` | `source_index` / `target_index` |
| `max_dist` | `max_distance` |

### `mapping_keys.py` (from `keys.py`)

| Before | After |
|---|---|
| `mkey` (param) | `normalized_key` |
| `mac` | `hmac_digest` |

### `aes_gcm_encryption.py` (from `encryption.py`)

| Before | After |
|---|---|
| `_aes` | `_cipher` |
| `blob` | `encrypted_envelope` |

### App-wide (same rule, applied package-by-package)

`pii_detection/`, `pseudonym_generation/`, `api/`, and top-level modules: expand single-letter loop
vars, local `d`/`e`/`m` abbreviations, and recognizer/builder shorthands per the rule. No file
renames outside the vault (their names — `engine`, `scoring`, `thresholds`, `inflection`,
`checksums`, `generator` — are already role-revealing). `dto.py`/`nlp.py` are retained as
conventional names (documented allowance in the rule).

---

## 4. Naming convention model (the rule's structure)

The deliverable `.claude/rules/python-naming-conventions.md` encodes:

- **File/module names** — descriptive & domain-oriented; mirror the dominant class when one exists;
  forbid generic names (`utils`, `helpers`, `common`, `misc`, `core`, `store`, `encryption`, `matching`).
- **Identifiers** — full words, no abbreviations; reveal intent so explanatory comments are unneeded.
- **Loop variables** — meaningful names, including inside algorithms (`current_row`, not `cur`).
- **Booleans** — `is_/has_/should_`. **Constants** — descriptive `UPPER_SNAKE`.
- **Acronyms** — keep domain acronyms (PII/PESEL/NIP/REGON/NRB/HMAC/TTL/AES/GCM), pair with a role
  word when it aids clarity (`aes_gcm_cipher`).
- **Before/after table** — sourced from §3 above (real examples from this refactor).
- **Frontmatter** — `paths: ["apps/gateway-api/**/*.py"]` so it auto-loads only for backend Python.
