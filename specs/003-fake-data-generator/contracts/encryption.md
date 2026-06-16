# Contract — Encryption & key strategy (`gateway_api/pseudonym_vault/encryption.py`, `keys.py`)

Implements Constitution III + spec FR-008/FR-026 and clarification Q1 (research D3/D4).

## Cipher: AES-256-GCM

```
encrypt(plaintext: bytes) -> bytes      # returns nonce(12) ‖ ciphertext ‖ tag(16)
decrypt(blob: bytes) -> bytes           # raises on tag mismatch / wrong key
```

- Library: `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
- Key: the 32 raw bytes from `base64decode(settings.redis_encryption_key)` — already validated to exactly
  32 bytes at startup (`config.py`), so the key length **is** AES-256.
- Nonce: fresh **96-bit** random per `encrypt` (`os.urandom(12)`), prepended to the blob.
- AEAD tag authenticates the blob (tamper-evident at rest).
- Plaintext is UTF-8 (JSON for structured records) encoded before encryption.

**Forbidden**: Fernet (AES-128-CBC) — would violate "AES-256". Fixed/reused nonces — catastrophic under
GCM.

## What is encrypted (clarification Q1)

| Data | Stored as |
|---|---|
| Original PII value (`orig_base`), `meta`, `forms`, `fwd` value (`fake_base`) | **encrypted** (`enc(...)`) |
| Fake forms used as `rev:` field names | **clear** (synthetic, not PII) |
| `fwd:` field names | **clear, non-reversible HMAC** (below) |

Net: no real personal data is recoverable from Redis (field names or values) without the key.

## Forward field-name HMAC (`keys.py`)

```
field_name = "fwd:" + hmac_sha256(key, f"{entity_type}|{mapping_key}").hexdigest()
```

- `key`: the same 32-byte system key (or an HKDF-derived subkey — implementation choice; same secret).
- `mapping_key`: per-type normalized form ([data-model §5](../data-model.md)) — spaCy lemma (PERSON/
  LOCATION), digits-only (identifiers), or case-folded text (address/email/phone).
- **Keyed** HMAC (not a bare SHA-256) so the tiny domains of identifiers (an 11-digit PESEL, a 9-digit
  phone) can't be reversed by precomputation/dictionary; an attacker without the key can't even confirm a
  guessed original is present (research D4).

## Properties verified by tests

- `test_encryption.py`: round-trip equality; two `encrypt` calls of the same plaintext yield **different**
  blobs (distinct nonces); `decrypt` with a different key fails; key length asserted 32 bytes.
- `test_keys.py`: separator variants of one identifier → identical `mapping_key` → identical HMAC (one
  mapping); same literal under two entity types → different HMAC (two mappings); HMAC field names contain
  no substring of the original (no PII in field names).
