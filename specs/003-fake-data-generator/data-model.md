# Phase 1 Data Model — EPIC 3: Fake-Data Generator & Reversible Session Mapping Store

Entities below are the contract the generation and mapping packages expose internally and the shape of
what is persisted in Redis. Field/key strings are confirmed by [research.md](research.md) and the
[contracts](contracts/). Nothing here is sent to an LLM (Epic 4).

---

## 1. `DetectedEntity` — Epic 2 DTO delta (`pii_detection/dto.py`)

Epic 2's model, **extended** with two optional fields (additive; default `None`, so Epic 2 callers and the
`/v1/detect` schema are unaffected).

| Field | Type | Notes |
|---|---|---|
| `entity_type` | `str` | unchanged (PERSON, LOCATION, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME, PESEL, NIP, REGON, POLISH_BANK_ACCOUNT, ADDRESS, …) |
| `start`, `end` | `int` | unchanged — offsets into the original text |
| `score` | `float` | unchanged |
| `text` | `str` | unchanged — exact matched substring |
| `metadata` | `dict` | unchanged — carries `gender` (PESEL), `variant` (REGON 9/14), normalized value, etc. |
| **`lemma`** | `str \| None` | **new.** Base form from spaCy; filled for PERSON/LOCATION only (research D1), else `None`. |
| **`case`** | `str \| None` | **new.** Grammatical case from `token.morph` `Case` (`Nom`/`Gen`/`Dat`/`Acc`/`Ins`/`Loc`); PERSON/LOCATION only, else `None`. |

**Population**: `pii_detection/engine.py` enrichment pass after overlap+threshold; multi-token PERSON spans
may expose a composite lemma that `pseudonym_generation` re-classifies per token (first vs last). Non-name types
are never enriched.

---

## 2. `FakeValue` — generator output (`pseudonym_generation/dto.py`)

The unit returned by `FakeDataGenerator.generate(entity)`. Immutable; **stateless** (no session
knowledge).

| Field | Type | Notes |
|---|---|---|
| `entity_type` | `str` | echoes the source entity type |
| `base` | `str` | the canonical/nominative fake (e.g. `"Nowak"`, `"90010112345"`, `"+48 601 234 567"`) |
| `forms` | `dict[str, str] \| None` | case→form map for PERSON/LOCATION (from `inflection.all_forms`); `None` for non-inflecting types |
| `gender` | `str \| None` | `"male"`/`"female"` for PERSON and PESEL (preserved from the original PESEL); else `None` |

**Validity invariants by type** (enforced in builders; see [contracts/generators.md](contracts/generators.md)):
- PESEL: passes `pesel_is_valid`; `pesel_gender(fake) == original gender`; post-2000 month offset handled.
- NIP / REGON / bank: pass `nip_is_valid` / `regon{9,14}_is_valid` / `nrb_is_valid`; REGON keeps the
  original's 9- vs 14-digit `variant`.
- PHONE_NUMBER: valid Polish format; DATE_TIME: `DD.MM.YYYY`, within ±10 years of the original.
- PERSON: first+last share one gender; surname constrained to a declinable pattern (post-filtered).
- ADDRESS: atomic single string; `forms = None` (not inflected).

---

## 3. `Pattern` + inflection tables (`pseudonym_generation/inflection.py`)

| Concept | Type | Notes |
|---|---|---|
| `Pattern` | enum/str | `ADJ_M` (-ski/-cki/-dzki), `ADJ_F` (-ska/-cka/-dzka), `NOUN_M_CONS`, `NOUN_F_A`, `CITY_M`, `CITY_F`, `CITY_N`, `INDECLINABLE` |
| `CASES` | tuple | `("nom","gen","dat","acc","ins","loc")` |
| suffix tables | `dict[Pattern, dict[case, (strip, add)]]` | fixed substitution rules; `INDECLINABLE` → base form for every case |

`classify(name, gender) -> Pattern`; `decline(base, pattern, case) -> str`;
`all_forms(base, pattern) -> {case: form}`. First name and surname are classified/declined independently.

---

## 4. `SessionMeta` (`pseudonym_vault/session.py`)

Stored (encrypted) in the hash's single `meta` field.

| Field | Type | Notes |
|---|---|---|
| `created_at` | ISO `str` | session creation time |
| `last_activity` | ISO `str` | refreshed on every successful op (mirrors the sliding TTL) |
| `entity_count` | `int` | number of distinct mappings held |
| `message_count` | `int` | number of pseudonymize/depseudonymize touches |

No personal data — but kept encrypted for uniformity (one envelope format for all field values).

---

## 5. Mapping — Redis HASH layout (`session:{session_id}`)

One HASH per session; one `EXPIRE` over the whole key (research D4/D5). **PII appears only inside encrypted
field VALUES.** `enc(...)` = AES-256-GCM envelope (§6).

| Field name | Value (decrypted) | Purpose |
|---|---|---|
| `fwd:{hmac}` | `fake_base` | forward lookup. `{hmac}` = `HMAC_SHA256(key, entity_type + "\|" + mapping_key)` hex (research D4) |
| `rev:{fake_form}` | `json{orig_base, case, entity_type}` | reverse lookup — **one field per inflected fake form**; field name is the synthetic fake form (safe in clear) |
| `forms:{fake_base}` | `json{case: fake_form, …}` | all inflected forms of a fake (for outgoing case rendering) |
| `meta` | `json` SessionMeta (§4) | lifecycle metadata |

**`mapping_key` by entity type** (the pre-HMAC normalized key — research D4):
| Type | `mapping_key` |
|---|---|
| PERSON, LOCATION | spaCy `lemma`, lowercased |
| PESEL, NIP, REGON, POLISH_BANK_ACCOUNT | `strip_separators` / `digits_only` (Epic 2 `normalization`) |
| ADDRESS, EMAIL_ADDRESS, PHONE_NUMBER | whitespace-normalized, case-folded text |

Consequences: a PESEL with or without dashes → identical `mapping_key` → one mapping (FR-024); the same
literal under two types → two different `entity_type` prefixes → two HMACs → two mappings (FR-025).

---

## 6. Encryption envelope (`pseudonym_vault/encryption.py`)

| Element | Value |
|---|---|
| algorithm | AES-256-GCM (`cryptography` `AESGCM`) |
| key | 32 raw bytes = `base64decode(REDIS_ENCRYPTION_KEY)` (validated in `config.py`) |
| nonce | fresh random 96-bit (12 bytes) per `encrypt` |
| stored blob | `nonce ‖ ciphertext ‖ tag` (GCM tag appended by `AESGCM.encrypt`) |
| plaintext | UTF-8 of the value (JSON for structured records) |

`encrypt(plaintext: bytes) -> bytes` and `decrypt(blob: bytes) -> bytes`; tampering fails the GCM tag.
Only original PII and `meta`/records are encrypted; **fake forms and HMAC field names are never
encrypted** (research D4).

---

## 7. `MappingStore` operations (`pseudonym_vault/store.py`) — state transitions

| Method | Effect | Spec |
|---|---|---|
| `get_or_create(session_id, entity) -> fake_form` | exact `fwd` hit → return cached; else PERSON/LOCATION coreference (D7); else generate (collision-safe D6), write `fwd`+`rev`(per form)+`forms`; **refresh TTL** | FR-007/012/013/014/015 |
| `get_original(session_id, fake_form) -> (orig, case) \| None` | exact `rev` hit → decrypt; else bounded fuzzy ≤2 (D8); **refresh TTL** | FR-007 |
| `get_all_mappings(session_id) -> list` | one `HGETALL` + decrypt → original↔fake pairs; **refresh TTL** | FR-011 |
| `delete_session(session_id)` | one `DEL` — removes all mappings at once | FR-010 |
| `extend_ttl(session_id)` | one `EXPIRE` — sliding refresh | FR-009 |

TTL applies to the whole hash; expiry or `DEL` removes every mapping together; a fresh `session_id` (or a
post-restart empty hash) behaves as an empty session (FR-027).

---

## 8. API request/response models (`api/pseudonymize.py`)

| Model | Fields |
|---|---|
| `PseudonymizeRequest` | `text: str`, `session_id: str \| None` |
| `Replacement` | `entity_type: str`, `original: str`, `fake: str`, `start: int`, `end: int` |
| `PseudonymizeResponse` | `pseudonymized_text: str`, `entities_replaced: list[Replacement]`, `session_id: str` |
| `DepseudonymizeRequest` | `text: str`, `session_id: str` |
| `DepseudonymizeResponse` | `restored_text: str`, `session_id: str` |

`session_id` is generated (and returned) when absent on pseudonymize. Full schema:
[contracts/pseudonymize.openapi.yaml](contracts/pseudonymize.openapi.yaml).
