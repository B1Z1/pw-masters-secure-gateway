# Contract: `GET` / `DELETE /v1/sessions/{session_id}` (session statistics + reset)

**Feature**: EPIC 6 | `gateway_api/api/sessions.py` (new router) + `MappingStore`/repository deltas.
Powers the dashboard (statistics) and the config panel's "reset session" (D8). **Not** gate-exempt
(needs Redis). No auth — anyone holding a `session_id` may read/delete it (documented limitation,
FR-026). Coexists with the EPIC 3 debug `GET /v1/sessions/{id}/mappings` (distinct path).

## `GET /v1/sessions/{session_id}` → 200

```jsonc
{
  "session_id": "…",
  "created_at": "2026-06-18T10:00:00+00:00",      // from SessionMeta
  "last_activity": "2026-06-18T10:05:00+00:00",   // from SessionMeta
  "ttl_remaining_seconds": 1500,                  // live Redis TTL of the session hash
  "entity_count": 3,                              // sum of entities_by_type (DISTINCT mappings)
  "entities_by_type": { "PERSON": 2, "PESEL": 1 },// distinct original↔fake mappings grouped by type
  "message_count": 1                              // successful chat round-trips (+1 per success)
}
```

| Field | Source |
|-------|--------|
| `created_at`, `last_activity`, `message_count` | `SessionMeta` (`read_meta`) |
| `entity_count`, `entities_by_type` | `get_all_mappings` (**distinct** pairs) grouped by `entity_type`; `entity_count` = sum — **not** `meta.entity_count` (a write counter) |
| `ttl_remaining_seconds` | `repository.ttl_seconds` (Redis `TTL`) |

## `DELETE /v1/sessions/{session_id}` → 200

```jsonc
{ "session_id": "…", "deleted": true }
```

Deletes the session hash and **all** its mappings (one Redis `DEL`), and discards the in-process session
lock. Reports success **only when the session existed**.

## 404 matrix (both verbs)

`{"detail": "session not found"}` (HTTP 404) when:
- the `session_id` is unknown, **or**
- the session's TTL expired (Redis evicted the hash), **or**
- the session detected **no PII ever** → no stored state ("nothing to manage", accepted — FR-021).

`GET` returns 404 when `get_session_summary` is `None` (no `meta`); `DELETE` returns 404 when
`delete_session` reports the key did not exist (`redis.delete` returned 0).

## Invariants

- `DELETE` is the session-reset control; after it, a subsequent `GET`/`DELETE` of the same id → 404.
- Logs carry `session_id` + counts only — never originals/fakes/content (Constitution VIII).
- A failed chat turn that wrote inbound mappings but errored at the provider leaves `entity_count>0`
  and `message_count==0` (D7) — the count reflects **successful** round-trips only.

## Acceptance assertions (map to spec)

- `GET` after a 2×PERSON + 1×PESEL turn → `entity_count==3`, `entities_by_type=={"PERSON":2,"PESEL":1}`,
  `message_count==1`, `ttl_remaining_seconds>0` (SC-005; FR-018/FR-019).
- `DELETE` removes session + mappings, then `GET`/`DELETE` → 404 (SC-005; FR-020).
- Unknown / TTL-expired / never-stored session → 404 on both verbs (SC-005; FR-021).
