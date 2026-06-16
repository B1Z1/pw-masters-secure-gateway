# Quickstart & Validation: EPIC 3 — Fake-Data Generator & Reversible Session Mapping Store

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

A run/validation guide proving the substitution + reversible-store round-trip works end to end.
Implementation details live in `tasks.md` (after `/speckit-tasks`) and the source; this file is how a
reviewer checks it. All commands run from the repo root unless noted. No LLM is involved.

## Prerequisites

- Epic 1 + Epic 2 working (`apps/gateway-api` runs; `GET /health` returns 200; `POST /v1/detect` works).
- **Redis running** (these routes REQUIRE it — unlike `/v1/detect`):
  ```bash
  docker compose up -d redis      # or the full stack
  ```
- New deps installed: `faker`, `cryptography` (runtime) and `fakeredis` (dev) added to
  `apps/gateway-api/pyproject.toml`:
  ```bash
  nx run gateway-api:install      # or: (cd apps/gateway-api && uv sync)
  ```
- **Polish model** present for native dev (baked into the container image):
  ```bash
  (cd apps/gateway-api && uv run python -m spacy download pl_core_news_lg)
  ```
- A valid `REDIS_ENCRYPTION_KEY` in `.env` (base64 of exactly 32 bytes) — already required by Epic 1.

## Run the unit + integration tests (no LLM; store tests use fakeredis)

```bash
nx run gateway-api:test          # → uv run pytest tests/
```

Expected green: `tests/pseudonym_generation/*` (per-type validity, PESEL gender + post-2000, REGON variant,
phone/date formats, inflection across six cases + indeclinable fallback, seed determinism),
`tests/pseudonym_vault/*` (AES-256-GCM round-trip & distinct nonces, key strategy, bounded fuzzy match,
fakeredis store: bidirectional / TTL refresh+expiry / delete / get_all / collision / coreference), and
`tests/test_pseudonymize_api.py` (round-trip incl. case change, session create, Redis-down 503, no-PII
logs). API/engine tests that need the model skip automatically if `pl_core_news_lg` is absent.

## Start the backend (native dev)

```bash
nx run gateway-api:serve         # uvicorn --reload on :8000 (Redis must be up)
```

---

## Validation scenarios

Map to the spec's user stories and success criteria. Endpoints:
[contracts/pseudonymize.openapi.yaml](contracts/pseudonymize.openapi.yaml).

### V1 — Replace + restore round-trip (US1, SC-001..SC-004)

```bash
# Forward: detect + substitute; capture the returned session_id
curl -s localhost:8000/v1/pseudonymize -H 'content-type: application/json' \
  -d '{"text":"Jan Kowalski, PESEL 90010112345, mieszka w Krakowie."}' | jq
```

Expect `pseudonymized_text` with a realistic fake name, a **checksum-valid** fake PESEL of the **same
gender**, and a fake city — plus `entities_replaced[]` and a new `session_id` (SC-001/SC-002). Verify the
fake PESEL passes its checksum and matches the original's gender (SC-002); a fake date elsewhere lands
within ±10 years (SC-003). Then reverse it (substitute the captured id):

```bash
curl -s localhost:8000/v1/depseudonymize -H 'content-type: application/json' \
  -d '{"text":"<pseudonymized_text>","session_id":"<session_id>"}' | jq
```

Expect `restored_text` equal to the original (SC-004). Empty input → empty result + a session, no error
(SC-011):

```bash
curl -s localhost:8000/v1/pseudonymize -H 'content-type: application/json' -d '{"text":""}' | jq
```

### V2 — Consistency across turns (US2, SC-005..SC-007)

Reuse one `session_id` across calls:
- Same original twice → **same fake** both times (SC-005).
- Turn 1 "Jan Kowalski"; turn 2 just "Kowalski" → resolves to the **same fake person** (SC-005).
- "Anna Kowalska" and "Jan Kowalski" → **distinct** fakes (SC-006).
- A PESEL once as `90010112345` and once as `900-101-123-45` → **one** fake (SC-006).
- The same literal under two entity types → **two** fakes (SC-006).
- No fake collides with another in the session (SC-007) — exercised by the seeded collision test.

### V3 — Polish inflection both ways (US3, SC-008)

```bash
curl -s localhost:8000/v1/pseudonymize -H 'content-type: application/json' \
  -d '{"text":"Sprawa Jana Kowalskiego z Krakowa.","session_id":"<sid>"}' | jq
```

Expect the genitive original recognised and the fake inserted in the **matching case** (e.g. "…Marka
Nowaka z Gdańska."); first name and surname inflected independently. Reverse → the original genitive forms
restored. A rare/foreign surname is mapped consistently but shown in **base form** (documented limitation).

### V4 — Secure store: TTL, clear, list, encryption (US4, SC-009..SC-011)

- **Encrypted at rest**: inspect Redis — `redis-cli HGETALL session:<sid>` shows `fwd:`/`rev:`/`forms:`/
  `meta` fields whose **values are ciphertext** and whose forward field names are HMAC hex; no original PII
  is readable (SC-009).
- **Reviewer listing**: the `get_all_mappings` surface returns the original↔fake pairs for review (SC-010).
- **Sliding TTL**: `redis-cli TTL session:<sid>` resets toward 1800s after each call (FR-009); with no
  activity it elapses and the session's mappings vanish (SC-010).
- **Explicit clear**: clearing the session removes all mappings at once (SC-010).
- **Restart**: `docker compose restart redis` mid-session → the session is gone; a new session starts
  fresh (SC-011, acceptable recovery).

### V5 — Redis gating

With Redis down, `POST /v1/pseudonymize` and `/v1/depseudonymize` return **503** (Epic 1 gate — these
routes are not exempt), while `/health` stays 200 and `/v1/detect` still serves.

### V6 — No PII in logs (Constitution VIII)

Run any call and inspect server logs: only `session_id`, entity **types/counts**, and timings appear —
never originals, fakes, or fake↔original pairs.

---

## Known limitations (Constitution IX)

See `apps/gateway-api/README.md` (Epic 3 section) and [research.md](research.md): no name↔PESEL gender
association (fake gender is random); no cross-field DOB coherence; inflection limited to common patterns
(rare/foreign → base form); address inflection not handled (atomic replacement); Redis restart loses the
session.
