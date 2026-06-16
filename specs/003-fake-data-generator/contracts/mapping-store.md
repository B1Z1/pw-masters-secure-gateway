# Contract — `MappingStore` (`gateway_api/pseudonym_vault/store.py`)

The reversible, encrypted, expiring session store. Async (Epic 1 `redis.asyncio`). All PII lives only
inside AES-256-GCM-encrypted field values; field names are non-reversible (HMAC) or synthetic (fake
forms). See [encryption.md](encryption.md), [research D4–D8](../research.md), [data-model §5](../data-model.md).

## Construction

- `get_mapping_store() -> MappingStore` — process singleton; holds the `get_redis_client()` handle and the
  AES key material (from `settings.redis_encryption_key`). MUST NOT raise when Redis is absent — operations
  fail/no-op gracefully (consistent with Epic 1 `dependencies.py`).

## Redis layout

One HASH per session at `session:{session_id}`; one `EXPIRE` covers it; default TTL `1800s` (FR-009,
`settings.redis_session_ttl`). Fields: `fwd:{hmac}`, `rev:{fake_form}`, `forms:{fake_base}`, `meta`
(see [data-model §5](../data-model.md)).

## Methods

### `async get_or_create(session_id, entity: DetectedEntity) -> str`
Returns the fake **form matching the entity's case** (PERSON/LOCATION) or the fake `base` otherwise.

1. Compute `mapping_key` (per-type, [data-model §5](../data-model.md)) and `fwd:{hmac}`.
2. **Exact hit** → decrypt `fake_base`; render the requested case from `forms:{fake_base}` (PERSON/LOCATION)
   or return base. Refresh TTL. Return.
3. **Coreference** (PERSON/LOCATION only, research D7): match `entity.lemma` by full-token containment
   against same-`entity_type` existing originals.
   - exactly one match → reuse that mapping (write a new `fwd:{hmac}` alias → same `fake_base`);
   - two or more → fall through to generation (new person — clarification Q2).
4. **Generate** (`FakeDataGenerator.generate`), collision-safe (research D6: retry ×3, then per-type
   fallback). Write `fwd:{hmac}` → `enc(fake_base)`, `forms:{fake_base}` → `enc(all_forms)`, and one
   `rev:{form}` → `enc({orig_base, case, entity_type})` per fake form (or just the base for non-inflecting
   types). Update `meta`. Refresh TTL. Return the case-matching form.

**Guarantees**: same original → same fake for the session (FR-012); separator variants collapse (FR-024);
same literal under two types stays distinct (FR-025); generated fake never collides within the session
(FR-015).

### `async get_original(session_id, fake_form: str) -> tuple[str, str] | None`
Returns `(orig_base, case)` or `None`. Exact `rev:{fake_form}` decrypt first; on miss, bounded
Levenshtein ≤ 2 over `rev:` field names (research D8). Refresh TTL. (Caller renders the original in the
matched form's case for PERSON/LOCATION.)

### `async get_all_mappings(session_id) -> list[dict]`
One `HGETALL` + decrypt → `[{entity_type, original, fake, forms}]` for reviewer inspection (FR-011).
Refresh TTL. (This is an in-process return value for the reviewer surface — never written to logs.)

### `async delete_session(session_id) -> None`
One `DEL session:{session_id}` — removes all mappings at once (FR-010). Idempotent.

### `async extend_ttl(session_id) -> None`
One `EXPIRE session:{session_id} <ttl>` — the sliding-refresh primitive (FR-009); called by every other
method on success.

## Cross-cutting

- **No PII in logs** (Constitution VIII / FR-026): log `session_id`, `entity_type`, counts, timings only —
  never originals, fakes, or pairs.
- **Redis down**: methods degrade (the route 503s at the gate before reaching the store); a missing/expired
  hash is treated as an empty session, no error (FR-027).
- **Restart**: hash gone → empty session; a new session starts fresh (FR-027, acceptable recovery).
