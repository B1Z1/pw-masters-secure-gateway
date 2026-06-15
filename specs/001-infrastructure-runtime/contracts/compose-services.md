# Contract: Docker Compose Topology

**Feature**: 001-infrastructure-runtime | Implements F-01 / FR-001–FR-013, FR-031–FR-033

Two files: `docker-compose.yml` (production/demo) and `docker-compose.override.yml` (dev, auto-merged by Compose). Project & network name: **`pw-masters-secure-gateway`**.

## Production stack — `docker-compose.yml`

| Service | Image / build | Host ports | Healthcheck | depends_on (condition) |
|---|---|---|---|---|
| `redis` | `redis:7-alpine`, password `${REDIS_PASSWORD}` | **none** (internal only) | `redis-cli ping` → PONG | — |
| `gateway-api` | build `./apps/gateway-api` (multi-stage) | `8000:8000` | `curl -f http://localhost:8000/health` | `redis: service_healthy` |
| `gateway-ui` | build `./apps/gateway-ui` (node→nginx) | `3000:80` | HTTP 200 on `/` | `gateway-api: service_healthy` |

**Network**: all three on the bridge network `pw-masters-secure-gateway`; services address each other by name (`redis`, `gateway-api`).

**Startup ordering contract (FR-004)**: `redis` healthy → `gateway-api` starts; `gateway-api` healthy → `gateway-ui` starts. Whole stack all-healthy within **60s** (SC-001).

**Security contract**: `redis` MUST have no `ports:` mapping in this file — unreachable from the host (SC-010, FR-003). `gateway-api` reads config via `env_file: .env`.

## Dev overrides — `docker-compose.override.yml` (auto-merged)

| Service | Override |
|---|---|
| `redis` | add `ports: ["6379:6379"]` so the natively-running backend can reach it (FR-009). |
| `gateway-api` | bind-mount `./apps/gateway-api/gateway_api:/app/gateway_api`; override `command:` to `uvicorn gateway_api.main:app --reload --host 0.0.0.0 --port 8000` (FR-010). |
| `gateway-ui` | add `profiles: ["production-only"]` → excluded from default `docker compose up`; dev runs Vite natively instead (FR-011). |

**Dev-mode contract**:
- `docker compose up` (override auto-applied) starts **redis + gateway-api** only; `gateway-ui` is held back by its profile.
- `docker compose up redis` starts only the store (FR-013) — the canonical "Terminal 1" for the three-terminal workflow.
- CI / true production pins the prod file explicitly: `docker compose -f docker-compose.yml up` (override ignored).

## Image build contracts

**`apps/gateway-api/Dockerfile` (multi-stage, FR-031–FR-033)**
- Stage 1 (builder): install deps with `uv`; `RUN python -m spacy download pl_core_news_lg` (built in, not downloaded at runtime — FR-033).
- Stage 2 (runtime): slim Python 3.12 base; copy only venv + `gateway_api/`; **non-root** user; `HEALTHCHECK ... --start-period=30s`.
- **Size**: Polish model baked in; **no size cap** (R1 resolved — budget relaxed by maintainer). Multi-stage build retained for hygiene; record the built size for reference.

**`apps/gateway-ui/Dockerfile` (multi-stage)**
- Stage 1: `node:20-alpine` → `npm ci && npm run build` → `dist/`.
- Stage 2: `nginx:1.25-alpine` serves `dist/` with `nginx.conf`: SPA fallback `try_files $uri $uri/ /index.html` + proxy `location /api/ { proxy_pass http://gateway-api:8000/; }` (FR-005).

## Acceptance hooks (verified in quickstart.md)

| Contract point | Check |
|---|---|
| Single-command startup, all healthy < 60s | `docker compose up` → `docker compose ps` all `healthy` |
| Redis not on host (prod) | `redis-cli -h localhost ping` fails / refused with prod file |
| API reachable | `curl localhost:8000/health` → 200 |
| UI reachable + proxy | `curl localhost:3000/` → SPA; UI's `/api/...` reaches backend |
| Dev override excludes UI | `docker compose up` starts redis + gateway-api only |
| Backend image builds | `docker images gateway-api` builds with model baked in; size recorded (no cap) |
