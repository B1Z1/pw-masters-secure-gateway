---
name: debug-services
description: >
  Debug the gateway's three services (redis, gateway-api, gateway-ui) in this Nx
  monorepo. Use when a service is unhealthy, /health is degraded, a route returns
  503, the stack won't start, hot-reload isn't working, or tests/lint fail. Knows
  the project's exact commands (docker compose, nx, uv, pytest/vitest).
---

# Debug services

Stack: **redis** (session store), **gateway-api** (FastAPI/uvicorn :8000),
**gateway-ui** (Vite dev :4200 / nginx :3000). Compose project & network:
`pw-masters-secure-gateway`. Prod file `docker-compose.yml`; dev override
`docker-compose.override.yml` (auto-merged, excludes `gateway-ui`, exposes Redis :6379).

## 0. First triage (always start here)

```bash
curl -s localhost:8000/health            # backend + dependency status (always HTTP 200)
npm run docker:ps                        # service status / health
```

Read `/health`:
- `{"status":"ok",...}` → backend & deps fine.
- `{"status":"degraded","dependencies":{"redis":"unavailable",...}}` → Redis is down/unreachable. **Non-health routes will return 503** by design (the `redis_availability_gate` middleware). Fix Redis, not the backend.
- `spacy_model` is a stub that always returns `"ok"` in Epic 1 — ignore it as a cause.
- No response / connection refused → backend isn't running or crashed at startup (see §3 fail-fast).

## 1. Docker stack

```bash
npm run docker:ps                                    # status + health column
npm run docker:logs                                  # follow all logs
docker compose -f docker-compose.yml logs gateway-api --tail=100
docker inspect --format '{{json .State.Health}}' pw-masters-secure-gateway-gateway-api-1 | jq

# exec into a container
docker compose -f docker-compose.yml exec gateway-api sh
docker compose -f docker-compose.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping   # -> PONG

# restart just one service / rebuild one image
docker compose -f docker-compose.yml restart gateway-api
docker compose -f docker-compose.yml up -d --build gateway-api

# Redis reachability FROM the api container (the in-network name is `redis`)
docker compose -f docker-compose.yml exec gateway-api \
  python -c "import socket; print(socket.gethostbyname('redis'))"
```

Startup ordering is healthcheck-gated: `redis healthy → gateway-api healthy → gateway-ui`.
If `gateway-api` is stuck "starting", check its logs for a config/fail-fast error (§3).

## 2. Native dev (hot reload)

```bash
docker compose up redis            # Terminal 1: Redis only (override exposes :6379)
nx run gateway-api:serve           # Terminal 2: uvicorn --reload :8000
nx run gateway-ui:serve            # Terminal 3: Vite HMR :4200 (proxies /api -> :8000)
```

Common native-dev issues:
- **`/health` shows `redis: unavailable`** → in `.env` the host must be `localhost`, not `redis`
  (the `redis` name only resolves inside Docker): `REDIS_URL=redis://:changeme@localhost:6379/0`.
- **Port already in use** → `lsof -i :8000` / `lsof -i :4200` / `lsof -i :6379`, then kill the stale process.
- **`/api/...` 404/connection refused in the SPA** → backend not up on :8000, or the Vite proxy
  rewrite (`/api` → ``) changed; see `apps/gateway-ui/vite.config.mts`.
- **Backend won't import** → run it directly to see the traceback:
  `cd apps/gateway-api && uv run --system-certs uvicorn gateway_api.main:app --port 8000`.

## 3. Fail-fast config errors (backend exits immediately)

The backend validates config at import (before binding a port). An invalid
`REDIS_ENCRYPTION_KEY` raises `ValueError` and uvicorn exits non-zero.

```bash
# Inspect the exact error natively:
cd apps/gateway-api
uv run --system-certs python -c "from gateway_api.config import get_settings; get_settings()"
```

- `REDIS_ENCRYPTION_KEY` MUST be base64 decoding to **exactly 32 bytes**. Regenerate:
  `python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
- `REDIS_PASSWORD` is required. Empty `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` are fine (no startup error).

## 4. Tests & lint

```bash
nx run-many --target=test                          # pytest (gateway-api) + vitest (gateway-ui)
nx run gateway-api:test                            # backend only
nx run gateway-ui:test                             # frontend only
nx run gateway-api:lint                            # ruff

# single backend test (full output, no cache):
cd apps/gateway-api && uv run --system-certs pytest tests/test_health.py::test_health_ok_when_redis_up -q

# single frontend test:
nx run gateway-ui:test -- src/app/app.spec.tsx
```

- Tests mock Redis (`gateway_api.health.get_redis_client`) — they never need a live Redis.
- Coverage/junit land in `coverage/` and `reports/` (gitignored).
- If a cached result hides a failure, append `--skip-nx-cache`.

## 5. Build / proxy note (pointer)

If `docker compose build` fails with `invalid peer certificate: UnknownIssuer`,
it's the corporate TLS-inspecting proxy — pass the CA at build time:
`CA_CERT_FILE=/path/corp-ca.pem npm run docker:build` (see README → "Building behind
a corporate TLS-inspecting proxy"). Behind the proxy, `uv` on the host needs
`--system-certs`.

## Symptom → likely cause

| Symptom | Look at |
|---|---|
| Non-health route → 503 | Redis down/unreachable (§0, §1, §2) — by-design gate, not a bug |
| `/health` 200 but `degraded` | Redis dependency only; backend itself is healthy |
| Backend exits on start | Fail-fast config (§3): bad `REDIS_ENCRYPTION_KEY` or missing `REDIS_PASSWORD` |
| `gateway-ui` missing from `docker compose up` | Expected in dev — it's behind the `production-only` profile; use the prod file |
| Native `/health` always degraded | `.env` `REDIS_URL` host should be `localhost` (§2) |
| Build cert error | Corporate proxy CA (§5) |
