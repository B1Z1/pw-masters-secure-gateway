# Quickstart & Validation Guide: Infrastructure and Runtime Environment

**Feature**: 001-infrastructure-runtime | **Date**: 2026-06-15

This guide proves Epic 1 works end to end. It maps each spec acceptance scenario / success criterion to a runnable check. Run it after implementation; it is the manual counterpart to the automated tests. Implementation code lives in the apps and in `tasks.md`, not here.

## Prerequisites

- Docker + Docker Compose v2
- Node 20 and npm (for native frontend dev)
- Python 3.12 and `uv` (for native backend dev)
- Nx CLI available via `npx nx` (installed with the workspace)

## Setup

```bash
cp .env.example .env
# Generate a valid 32-byte AES key and paste it into REDIS_ENCRYPTION_KEY:
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# Edit .env: set REDIS_ENCRYPTION_KEY (and REDIS_PASSWORD if changed).
```

---

## Scenario A — One-command full-stack startup (US1 / SC-001, SC-010)

```bash
docker compose -f docker-compose.yml up -d   # prod file = include gateway-ui
docker compose -f docker-compose.yml ps
```

**Expected**:
- Within **60s**, all three services report `healthy`.
- `curl -s localhost:8000/health` → `{"status":"ok","dependencies":{"redis":"ok","spacy_model":"ok"}}` (HTTP 200).
- `curl -s localhost:3000/` → SPA HTML ("LLM Gateway").
- Redis is NOT reachable from the host: `redis-cli -h localhost -p 6379 ping` → connection refused (SC-010).
- The UI's `/api/...` calls reach the backend (click the health-ping button in the SPA → shows backend status).

Startup ordering (FR-004): `docker compose logs` shows `redis` healthy before `gateway-api` starts, and `gateway-api` healthy before `gateway-ui`.

Teardown: `docker compose -f docker-compose.yml down`.

---

## Scenario B — Local hot-reload dev mode (US2 / SC-005, SC-008)

Three terminals:

```bash
# Terminal 1 — only Redis (override exposes 6379 on host)
docker compose up redis

# Terminal 2 — native backend with hot reload
nx run gateway-api:serve            # → uvicorn ... --reload on :8000

# Terminal 3 — native frontend with hot reload
nx run gateway-ui:serve             # → Vite dev server (Nx default :4200), proxies /api → :8000
```

**Expected**:
- Edit a string in `apps/gateway-api/gateway_api/health.py` → uvicorn reloads; next `/health` shows the change — **no image rebuild** (SC-005).
- Edit `apps/gateway-ui/src/App.tsx` → browser hot-reloads instantly (SC-005).
- Vite dev server at `localhost:4200` (Nx default); its `/api/...` requests reach the native backend on `:8000` (FR-012).
- `nx run gateway-api:serve` and `nx run gateway-ui:serve` each start their server individually (SC-008).

Also verify the override excludes the UI container (FR-011):
```bash
docker compose up -d            # override auto-merged
docker compose ps               # → redis + gateway-api only; NO gateway-ui
```

---

## Scenario C — Health observability & graceful degradation (US3 / SC-004)

With the stack running (Scenario A):

```bash
docker compose -f docker-compose.yml stop redis      # kill the dependency
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health    # → 200
curl -s localhost:8000/health     # → status "degraded", redis "unavailable"
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/v1/anything  # → 503 (gate)
# backend process is still alive (no crash):
docker compose -f docker-compose.yml ps gateway-api   # → still Up
docker compose -f docker-compose.yml start redis      # restore
curl -s localhost:8000/health     # → back to "ok" WITHOUT restarting gateway-api
```

**Expected**: matches SC-004 exactly — `/health` stays 200/degraded, non-health → 503, zero crashes, automatic recovery.

---

## Scenario D — Fail-fast on invalid encryption key (US3 / SC-003)

```bash
# Native (fastest signal):
cd apps/gateway-api
REDIS_ENCRYPTION_KEY="not-base64!!" uv run uvicorn gateway_api.main:app --port 8000; echo "exit=$?"
```

**Expected**: process exits **non-zero within 5s** with a `ValueError` about the encryption key (base64/32-byte). No HTTP server ever binds (SC-003, FR-019).

Also verify the optional-keys rule (FR-020): starting with empty `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` succeeds — no startup error.

---

## Scenario E — Backend image builds with model baked in (SC-006)

```bash
docker compose -f docker-compose.yml build gateway-api
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep gateway-api
```

**Expected**: image builds successfully with `pl_core_news_lg` baked in and `/health` reachable; size is **recorded for reference, not gated** (R1 resolved — the maintainer relaxed the size budget; multi-stage build is still used for hygiene).

---

## Scenario F — Automated tests (SC-007)

```bash
nx run-many --target=test            # pytest (gateway-api) + vitest (gateway-ui)
```

**Expected**: both suites run and pass. Backend `test_health.py` covers:
1. `/health` → 200 + `ok` when Redis ping succeeds (mocked)
2. `/health` → 200 + `degraded` when Redis ping raises `ConnectionError`
3. Non-health route → 503 when Redis unavailable
4. `Settings()` with invalid `REDIS_ENCRYPTION_KEY` raises `ValueError`
5. `Settings()` with missing `OPENAI_API_KEY` does NOT raise

---

## Coverage map (scenario → spec)

| Scenario | Spec coverage |
|---|---|
| A | US1; SC-001, SC-010; FR-001–FR-007 |
| B | US2; SC-005, SC-008; FR-008–FR-015 |
| C | US3; SC-004; FR-022–FR-029 |
| D | US3; SC-003; FR-019, FR-020 |
| E | SC-006; FR-031–FR-033 |
| F | SC-007; FR-014, health behaviors |
