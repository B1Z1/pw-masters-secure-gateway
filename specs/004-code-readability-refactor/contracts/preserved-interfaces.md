# Contract — Preserved Interfaces (Regression Surface)

This refactor is behavior-preserving. The items below are **frozen**: they must be byte/▶signature
identical before and after. They are the contract the existing test suite enforces (FR-006, FR-007,
SC-003). Anything not listed here is internal and may be reorganized/renamed freely.

## 1. `MappingStore` — public Python API (file moves `store.py` → `mapping_store.py`)

Constructor (positional; used by `tests/conftest.py::make_store` and `test_collision_free`):

```python
MappingStore(redis, encryptor, key_bytes, ttl, generator)
```

Methods — names, parameters, async-ness, and return shapes unchanged:

| Method | Returns |
|---|---|
| `async get_or_create(session_id: str, entity: DetectedEntity) -> str` | the fake surface form to substitute |
| `async get_original(session_id: str, fake_form: str) -> dict \| None` | `{orig_base, case, entity_type, [exact]}` or `None` |
| `async get_all_mappings(session_id: str) -> list[dict]` | items `{entity_type, original, fake}` |
| `async restore_text(session_id: str, text: str) -> str` | text with every fake replaced by its original |
| `async delete_session(session_id: str) -> None` | — |
| `async extend_ttl(session_id: str) -> None` | — |

Module-level:

```python
def get_mapping_store() -> MappingStore | None   # process-wide singleton over the Epic 1 Redis client
```

Re-exports from `pseudonym_vault/__init__.py` stay: `MappingStore`, `get_mapping_store`.

## 2. `Encryptor` — public API (file moves `encryption.py` → `aes_gcm_encryption.py`)

```python
class Encryptor:
    def __init__(self, key: bytes) -> None          # raises ValueError if len(key) != 32
    def encrypt(self, plaintext: bytes) -> bytes
    def decrypt(self, blob: bytes) -> bytes

def key_from_settings(settings) -> bytes
```

The new `EncryptedJsonCodec` is **additive** — it wraps `Encryptor` and must not alter `Encryptor`'s
behavior. Class names `MappingStore` and `Encryptor` are unchanged (cited in
`specs/003-fake-data-generator/contracts/`).

## 3. HTTP routes — unchanged (`api/pseudonymize.py`)

Only the import path `from ..pseudonym_vault.store import get_mapping_store` updates to
`...mapping_store import get_mapping_store`. Route paths, request/response models, and status codes
stay:

- `POST /v1/pseudonymize` → `PseudonymizeResponse{pseudonymized_text, entities_replaced[], session_id}`
- `POST /v1/depseudonymize` → `DepseudonymizeResponse{restored_text, session_id}`
- `GET /v1/sessions/{session_id}/mappings` → `SessionMappingsResponse{session_id, mappings[]}`

## 4. Redis wire format — unchanged (no migration)

One HASH per session, key `session:{id}`. Field schema (from `session_layout.py`) byte-identical:

| Prefix / field | Value |
|---|---|
| `fwd:{hmac}` | `enc(fake_base)` — HMAC-SHA256 forward field name; value AES-GCM encrypted |
| `rev:{fake_form}` | `enc(json{orig_base, case, entity_type[, exact]})` |
| `forms:{fake_base}` | `enc(json{case: fake_form, ...})` |
| `meta` | `enc(json SessionMeta{created_at, last_activity, entity_count, message_count})` |
| `corefs` | `enc(json[{lemma, fake_base, entity_type}])` |

Constraint: a session written **before** the refactor must remain fully readable after it.

## 5. Encryption envelope — unchanged

AES-256-GCM, 32-byte key, envelope `nonce(12) ‖ ciphertext ‖ tag`. Only ORIGINAL PII is encrypted;
synthetic fakes and HMAC field names stay in clear (Constitution III). Forward field = `fwd:` +
HMAC-SHA256(key, `"{entity_type}|{normalized_key}"`).

## 6. Logging — unchanged (Constitution VIII)

Log statements continue to emit `session_id`, entity types, and counts only — never originals or
fakes. Guarded by `test_encrypted_at_rest_no_pii_in_names_or_values`.

---

**Verification**: `apps/gateway-api/tests/` passes with **no assertion changes** — only import
statements and renamed test-file names. See [../quickstart.md](../quickstart.md).
