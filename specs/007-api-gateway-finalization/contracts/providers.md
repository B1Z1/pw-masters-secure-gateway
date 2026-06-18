# Contract: `GET /v1/providers` (provider discovery)

**Feature**: EPIC 6 | `gateway_api/api/providers.py` (new router) + `main.py` (gate-exempt). Read-only;
config panel populates provider choice + key-presence warning **before** the first message (D9). No
Redis dependency → **gate-exempt** (answers even while Redis is down).

## Request

`GET /v1/providers` — no parameters, no body, no auth (prototype).

## Response (HTTP 200)

```jsonc
[
  { "name": "openai",    "requires_key": true,  "key_configured": true  },
  { "name": "anthropic", "requires_key": true,  "key_configured": false },
  { "name": "ollama",    "requires_key": false, "key_configured": false }
]
```

| Field | Rule |
|-------|------|
| `name` | one of `openai`, `anthropic`, `ollama` (the three providers behind the router) |
| `requires_key` | `true` for `openai`/`anthropic`; `false` for `ollama` (local, keyless) |
| `key_configured` | `bool(settings.openai_api_key)` / `bool(settings.anthropic_api_key)`; always `false` for `ollama` |

## Invariants

- **No secret ever crosses the boundary**: only the booleans above; never a key value or any other
  secret (FR-012). Keys are server-side `.env` only and are never accepted from the client.
- **Stateless**: derived purely from `Settings`; no Redis, no provider network call. Added to
  `_GATE_EXEMPT_PATHS` so the config panel renders in a degraded stack (consistent with `/health`,
  `/v1/detect`).
- No model-name catalog (EPIC 5 routes by prefix with no registry — D9).

## Acceptance assertions (map to spec)

- Three entries with correct `requires_key`/`key_configured` reflecting the `.env` (SC-006; FR-011).
- No key value in the body; keys never client-supplied (SC-006; FR-012).
- Answers while Redis is down (gate-exempt).
