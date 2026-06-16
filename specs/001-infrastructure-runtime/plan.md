# Implementation Plan: EPIC 1 — Infrastructure and Runtime Environment

**Branch**: `001-infrastructure-runtime` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-infrastructure-runtime/spec.md`

## Summary

Stand up the foundational runtime for the anonymization gateway as an Nx monorepo: a Python 3.12 / FastAPI backend (`gateway-api`), a React 18 + Vite SPA (`gateway-ui`), and a Redis session store, all started with one `docker compose up`. The epic delivers (F-01) a three-service Compose stack on an internal `pw-masters-secure-gateway` network with healthcheck-gated startup ordering and a dev-mode override for native hot-reload development; (F-02) environment-driven configuration via `pydantic-settings` with fail-fast validation of the 32-byte AES key; and (F-03) a `GET /health` endpoint that always returns HTTP 200 while reporting per-dependency status, plus middleware that returns 503 on non-health routes when Redis is down. No PII/NER/LLM logic is built here; the SpaCy model check is a replaceable stub.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x on Node 20 (frontend)

**Primary Dependencies**: FastAPI + uvicorn, `pydantic-settings`, `redis` (async redis-py), `httpx`; React 18 + Vite; build/test via Nx 19+ with `@nx/react` and `@nxlv/python` (uv package manager); pytest (backend), vitest (frontend); nginx (frontend runtime)

**Storage**: Redis 7 (session/mapping store — in this epic used only for liveness ping and as the gating dependency; encrypted mapping data arrives in Epic 3)

**Testing**: pytest (`gateway-api`), vitest (`gateway-ui`), orchestrated by `nx run-many --target=test`

**Target Platform**: Docker Compose on a single host (Linux containers); local dev on macOS/Linux host with native uvicorn + Vite

**Project Type**: Web application (frontend + backend) in an Nx integrated monorepo; no shared `libs/` in this epic

**Performance Goals**: full stack all-healthy < 60s; `GET /health` < 500ms; invalid encryption key → non-zero exit < 5s

**Constraints**: backend image size **uncapped** (Polish model baked in; R1 resolved — budget relaxed by maintainer); Redis never published to host in the production stack; no secrets/PII in logs; synchronous request/response only; single-command startup with no manual steps beyond `.env`

**Scale/Scope**: thesis/demo scale, single host, 3 services, 0 shared libraries this epic

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0. This is an infrastructure epic — most data-handling principles are not yet exercised, but the foundation must not foreclose them. Gate evaluation:

| Principle | Applicability to Epic 1 | Status |
|-----------|------------------------|--------|
| I. Privacy by Design | No outbound LLM traffic yet; no bypass path introduced. Middleware ensures the app cannot serve work routes without its session store. | ✅ Pass |
| II. Recall over Precision | No detection in this epic. | ✅ N/A |
| III. Reversibility within Session | Establishes the encrypted Redis store foundation: `REDIS_ENCRYPTION_KEY` validated as 32 bytes (AES-256 key material) and `REDIS_SESSION_TTL` configured. No mapping logic yet. | ✅ Pass |
| IV. Provider Agnosticism | Config carries OpenAI/Anthropic/Ollama credentials + `DEFAULT_LLM_PROVIDER`/`DEFAULT_MODEL`; no provider coupling in infrastructure. | ✅ Pass |
| V. Synchronous Only | No streaming introduced anywhere. | ✅ Pass |
| VI. Polish First | Backend image bakes in the Polish model `pl_core_news_lg` at build time (FR-033) so Epic 2 NER is Polish-ready; image size is uncapped (R1 resolved). | ✅ Pass |
| VII. Realistic Substitution | No substitution in this epic. | ✅ N/A |
| VIII. No PII in Logs | FR-030: logs carry only operational metadata; secrets (encryption key, Redis password) never logged. | ✅ Pass |
| IX. Simplicity over Completeness | SpaCy health check is a documented stub returning `"ok"`, replaced in Epic 2 without touching endpoint logic. | ✅ Pass |

**Technology Constraints**: Python 3.12 + FastAPI ✅, Presidio+SpaCy `pl_core_news_lg` (model present, engine wired later) ✅, Redis + AES-256 key ✅, React SPA ✅, Docker/Compose ✅, multi-provider config ✅. No deviations.

**Gate result: PASS.** No entries required in Complexity Tracking. The earlier image-size tension (R1) is **resolved** — the maintainer relaxed the size budget, so the Polish model is baked in unconditionally; see [research.md](research.md).

## Project Structure

### Documentation (this feature)

```text
specs/001-infrastructure-runtime/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — decisions & risks
├── data-model.md        # Phase 1 output — config/service/health entities
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/           # Phase 1 output
│   ├── health.openapi.yaml      # GET /health + 503 gate contract
│   ├── environment.md           # .env variable contract
│   └── compose-services.md      # service/network/healthcheck contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
.                                   # Nx workspace root (greenfield — scaffolded in Phase 0)
├── nx.json                         # Nx config: plugins + targetDefaults caching
├── package.json                    # root: nx, @nx/react, @nxlv/python devDeps
├── tsconfig.base.json              # shared TS paths
├── docker-compose.yml              # production/demo stack (3 services)
├── docker-compose.override.yml     # dev-mode overrides (auto-merged)
├── .env.example                    # committed, every var documented inline
├── .env                            # gitignored, never committed
├── .gitignore
├── README.md
│
├── apps/
│   ├── gateway-api/                # @nxlv/python uv-project (application)
│   │   ├── project.json            # Nx targets: serve, test, lint, build
│   │   ├── pyproject.toml          # uv-managed deps
│   │   ├── .python-version         # 3.12
│   │   ├── Dockerfile              # multi-stage (deps+model → slim runtime)
│   │   ├── gateway_api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # FastAPI app + Redis-availability middleware
│   │   │   ├── config.py           # pydantic-settings BaseSettings + key validator
│   │   │   ├── health.py           # GET /health router + check functions
│   │   │   └── dependencies.py     # async Redis client singleton
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_health.py
│   │       └── test_observability.py   # US3: no-secrets-in-logs + /health perf sanity
│   │
│   └── gateway-ui/                 # @nx/react application (Vite)
│       ├── project.json            # Nx targets: dev, build, test, lint
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts          # dev proxy /api → localhost:8000
│       ├── Dockerfile              # multi-stage: node build → nginx serve
│       ├── nginx.conf              # SPA fallback + /api/ proxy → gateway-api:8000
│       └── src/
│           ├── main.tsx
│           └── App.tsx             # placeholder: "LLM Gateway" + /health ping
```

**Structure Decision**: Nx integrated monorepo, `apps`-preset, with the two applications under `apps/` exactly as the spec's monorepo layout prescribes. No shared `libs/` are introduced in this epic (none needed). The workspace is greenfield — the repo root currently holds only `.git`, `.specify`, `.claude`, `docs/`, `specs/`, `CLAUDE.md`, `README.md` — so Phase 0 generates the workspace in a **temporary subfolder and then moves the files up to the repo root**, preserving `.git`/`docs`/`specs`/`.specify` (see [research.md](research.md) decision D1).

## Implementation Phases

These phases drive the eventual `tasks.md` (produced by `/speckit-tasks`). Each phase is independently verifiable.

- **Phase 0 — Workspace scaffold**: Generate the Nx workspace in a temp subfolder then move files up to the repo root (D1), install `@nx/react` + `@nxlv/python`, generate `gateway-ui` (Vite/vitest) and `gateway-api` (uv-project, Python 3.12), author `.env.example` and `.gitignore`, configure `nx.json` caching + per-project targets. *Verify*: `nx show projects` lists both; `nx graph` renders.
- **Phase 1 — Backend config + health** (order-sensitive): `config.py` (settings + base64/32-byte key validator that raises on import) → `dependencies.py` (lazy async Redis client, never raises on construction) → `health.py` (`/health` router; Redis ping with 1s timeout; `check_spacy_model()` stub returning `"ok"`; aggregation to `ok`/`degraded`; always HTTP 200) → `main.py` (app wiring + `redis_availability_gate` middleware exempting only `/health`) → `tests/test_health.py` (the five spec cases). *Verify*: `nx run gateway-api:test` green.
- **Phase 2 — Backend Dockerfile**: multi-stage build with `uv`, `pl_core_news_lg` downloaded at build time, non-root runtime user, `HEALTHCHECK` with `--start-period=30s`. *Verify*: image builds; `/health` reachable; record image size for reference (no cap — R1 resolved).
- **Phase 3 — Frontend scaffold + Dockerfile**: `vite.config.ts` dev proxy `/api` → `localhost:8000`; minimal `App.tsx` with a health-ping button; `nginx.conf` SPA fallback + `/api/` proxy → `gateway-api:8000`; two-stage `node:20-alpine` → `nginx:1.25-alpine` Dockerfile. *Verify*: `nx run gateway-ui:build`; container serves SPA + proxies API.
- **Phase 4 — Compose files**: `docker-compose.yml` (named project + internal network, Redis unexposed with `redis-cli` healthcheck, `gateway-api` with `env_file` + `/health` healthcheck + `depends_on redis: service_healthy`, `gateway-ui` `3000:80` + `depends_on gateway-api: service_healthy`); `docker-compose.override.yml` (Redis `6379:6379`, backend source mount + `--reload` command, `gateway-ui` behind `production-only` profile). *Verify*: full-stack acceptance scenarios in [quickstart.md](quickstart.md).
- **Phase 5 — README**: prerequisites, quickstart, key-generation one-liner, three-terminal dev workflow, Nx command reference, health verification.

## Key Technical Decisions

Recorded in full (decision + rationale + alternatives) in [research.md](research.md). Summary:

| Decision | Rationale |
|---|---|
| Scaffold Nx in a temp subfolder, then move files up to root | Repo already initialized with `.git`/`docs`/`specs`; nesting would break paths. Subfolder-then-move chosen by maintainer. (research D1) |
| `docker-compose.override.yml` for dev | Auto-merged by Compose; zero extra flags in dev; CI pins prod with `-f docker-compose.yml`. |
| SpaCy check stubbed in Epic 1 | Avoids model load/startup penalty in an epic with no NER; `check_spacy_model()` body swapped in Epic 2 (Constitution IX). |
| `gateway-ui` excluded from dev via `production-only` profile | Devs use Vite HMR locally; the container has no HMR and would contend for the port. |
| Redis never host-published in prod | Security: the store must be unreachable outside the Docker network when deployed (SC-010). |
| Fail-fast on bad encryption key (`ValueError` at settings import) | A silent start with broken AES-256 is worse than no start (Constitution III). |
| uv for Python deps | Native to `@nxlv/python`; fast; lockfile reproducibility. |
| `targetDefaults` caching over legacy `cacheableOperations` | Nx 19+ idiom for `build`/`test`/`lint`; `serve`/`dev` left uncached. (research D2) |

## Complexity Tracking

> No constitution violations. Section intentionally empty.
