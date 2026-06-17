---
paths:
  - "apps/gateway-api/**/*.py"
---

# Python Naming Conventions (gateway-api backend)

Code must read like prose: a reader should understand a line without an explanatory comment.
These rules are mandatory for all Python under `apps/gateway-api/`. They were derived from the
004 readability refactor; the before/after table at the end shows real examples from that work.

## 1. File / module names

- Names describe the **domain or role**, not a generic category.
- When a module is dominated by one class, mirror it (`MappingStore` → `mapping_store.py`).
- Prefer a name that says *what kind* (`aes_gcm_encryption.py`, not `encryption.py`;
  `coreference_matching.py`, not `matching.py`).
- **Forbidden** generic module names: `utils`, `helpers`, `common`, `misc`, `core`, `store`,
  `encryption`, `matching`, `manager`, `stuff`.
- Conventional, widely-understood names are allowed (`dto.py`, `nlp.py`, `config.py`, `main.py`).

## 2. Variables, parameters, attributes

- Use **full words** that reveal intent. No truncations or cryptic shorthands.
  - `session_key`, not `hkey`; `normalized_key`, not `mkey`; `forward_field_name`, not `fwd`;
    `encryptor`, not `enc`; `reverse_record`, not `rec`; `original_base`, not `ob`;
    `encrypted_value`, not `blob`.
- A name that reveals intent removes the need for a "what this does" comment. Keep comments for
  **why** (rationale, references, constitution notes) — not for restating the code.
- Private attributes follow the same rule: `self._generator`, not `self._gen`;
  `self._encryption_key`, not `self._key`; `self._session_ttl_seconds`, not `self._ttl`.

## 3. Loop variables

- Always meaningful — including inside tight algorithms and comprehensions.
  - `for token in tokens:` not `for t in tokens:`
  - `for entity in entities:` not `for e in entities:`
  - `for result in results:` not `for r in results:`
  - `for grammatical_case in CASES:` not `for c in CASES:`
- In algorithms, name the role: `current_row` / `previous_row` (not `cur` / `prev`),
  `source_char` / `target_char` (not `ca` / `cb`), `edit_distance` (not `val`).

## 4. Booleans

- Prefix with `is_` / `has_` / `should_` / `can_`: `is_inflecting_name`, `has_forms`,
  `should_retry`.

## 5. Constants

- Descriptive `UPPER_SNAKE_CASE`: `MAX_GENERATION_ATTEMPTS`, `NONCE_BYTES`.
- **Exception — wire-format / protocol literals are frozen**: Redis field prefixes and similar
  on-the-wire constants (`FWD = "fwd:"`, `REV = "rev:"`, `FORMS = "forms:"`, `META = "meta"`) keep
  their exact string values; rename the *variables* that hold them, never the literal values.

## 6. Acronyms

- Keep established domain acronyms: PII, PESEL, NIP, REGON, NRB, HMAC, TTL, AES, GCM, AEAD.
- Pair an acronym with a role word when it aids clarity: `aes_gcm_cipher`, `hmac_digest`,
  `session_ttl_seconds`.
- Acronyms are **not** an excuse to abbreviate ordinary words.

## 7. Enforcement

- Reviewed by hand — `ruff` is configured for E/F/UP/B/SIM/I and does **not** flag abbreviations
  (pep8-naming `N` is not enabled). Treat this rule as the standard a reviewer (or agent) applies.

## Before / after (from the 004 refactor)

| Before | After | Where |
|--------|-------|-------|
| `hkey` | `session_key` | `mapping_store.py` |
| `mkey` | `normalized_key` | `mapping_store.py`, `mapping_keys.py` |
| `fwd` | `forward_field_name` | `mapping_store.py` |
| `_enc` | `_codec` / via `EncryptedJsonCodec` | `mapping_store.py` |
| `_gen` | `_generator` | `mapping_store.py` |
| `_key` | `_encryption_key` | `mapping_store.py` |
| `_ttl` | `_session_ttl_seconds` | `mapping_store.py` |
| `ob` | `original_base` | `mapping_store.py` |
| `rec` | `reverse_record` | `mapping_store.py` |
| `blob` | `encrypted_value` / `encrypted_envelope` | `mapping_store.py`, `aes_gcm_encryption.py` |
| `fmap` | `forms_by_case` | `mapping_store.py` |
| `d` / `best_d` | `distance` / `best_distance` | `mapping_store.py` |
| `cset` / `sset` | `candidate_tokens` / `stored_tokens` | `coreference_matching.py` |
| `cs` / `ss` | `candidate_set` / `stored_set` | `coreference_matching.py` |
| `cur` / `prev` | `current_row` / `previous_row` | `coreference_matching.py` |
| `idxs` | `matched_indices` | `coreference_matching.py` |
| `mac` | `hmac_digest` | `mapping_keys.py` |
| `_aes` | `_cipher` | `aes_gcm_encryption.py` |
| `for c in CASES` | `for grammatical_case in CASES` | `inflection.py`, builders |
| `for e in entities` | `for entity in entities` | `engine.py`, `api/` |
| `for r in results` | `for result in results` | recognizers |
