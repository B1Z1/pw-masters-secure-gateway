---
description: "Task list for EPIC 1 — Infrastructure and Runtime Environment"
---

# Tasks: EPIC 1 — Infrastructure and Runtime Environment

**Input**: Design documents from `specs/001-infrastructure-runtime/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: INCLUDED. The spec & plan explicitly request backend unit tests (`test_health.py`, 5 cases). They live with the code they exercise (Foundational phase) and are re-referenced by the user stories whose guarantees they prove.

**Organization**: Tasks are grouped by user story. Because this is an infrastructure epic, the backend runtime core (config + Redis client + `/health` + middleware) is a hard prerequisite for all three stories and is therefore placed in **Foundational (Phase 2)** — see the Dependencies section for the one cross-story note.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)

## Path Conventions

Nx monorepo (web app): backend at `apps/gateway-api/`, frontend at `apps/gateway-ui/`, orchestration & config at the repo root. Paths below are repo-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Greenfield Nx workspace + both project skeletons + environment scaffolding.

- [X] T001 Generate the Nx workspace into a temporary subfolder then move files (`nx.json`, `package.json`, `package-lock.json`, `tsconfig.base.json`, `.nx/`) up to the repo root, preserving `.git/`, `docs/`, `specs/`, `.specify/`, `.claude/`, `CLAUDE.md` (per [research.md](research.md) D1). Run `nx show projects` to verify.
- [X] T002 Install plugins as devDependencies in root `package.json`: `npm install --save-dev @nx/react @nxlv/python`
- [X] T003 [P] Generate the frontend app at `apps/gateway-ui/`: `nx g @nx/react:application gateway-ui --bundler=vite --style=css --unitTestRunner=vitest --directory=apps/gateway-ui --no-interactive`
- [X] T004 [P] Generate the backend app at `apps/gateway-api/`: `nx g @nxlv/python:uv-project gateway-api --projectType=application --packageName=gateway-api --moduleName=gateway_api --directory=apps/gateway-api --pyenvPythonVersion=3.12 --no-interactive`
- [X] T005 Configure caching in `nx.json` via `targetDefaults` (`build`, `test`, `lint` → `"cache": true`; leave `serve`/`dev` uncached) per [research.md](research.md) D2 — run after generators to avoid clobbering project-graph edits
- [X] T006 [P] Create `.env.example` at the repo root with all 9 variables and inline documentation exactly per [contracts/environment.md](contracts/environment.md) (placeholders only — never a real key)
- [X] T007 [P] Create/merge root `.gitignore` to ignore `.env`, `.nx/cache`, `dist/`, `node_modules/`, `.venv/`, `__pycache__/` (satisfies SC-009: `.env` never committed)

**Checkpoint**: `nx show projects` lists `gateway-api` and `gateway-ui`; `nx graph` renders.

---

## Phase 2: Foundational (Backend Runtime Core — Blocking Prerequisites)

**Purpose**: The backend application that every user story builds on. Implements config validation (F-02), the `/health` surface (F-03), and the Redis-availability gate. This is also where US3's guarantees are implemented and unit-tested.

**⚠️ CRITICAL**: No user story can be containerized (US1), dev-served (US2), or validated (US3) until this phase is complete.

- [X] T008 Add runtime + dev dependencies to `apps/gateway-api/pyproject.toml`: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `redis`, `httpx`, `spacy`; dev group `pytest`, `pytest-asyncio`, `flake8`. Run `uv sync` to produce the lockfile
- [X] T009 Implement `apps/gateway-api/gateway_api/config.py`: `pydantic-settings` `Settings(BaseSettings)` with all fields from [data-model.md](data-model.md); a field validator for `redis_encryption_key` that base64-decodes and asserts exactly 32 bytes, raising `ValueError` otherwise (FR-019); LLM keys `Optional[str] = None` with no validation (FR-020)
- [X] T010 Implement `apps/gateway-api/gateway_api/dependencies.py`: a lazily-constructed async `redis.Redis` client built from `redis_url`, exposed via `get_redis_client()`; construction must NOT raise on missing/bad URL (FR-028, research D4)
- [X] T011 Implement `apps/gateway-api/gateway_api/health.py`: an `APIRouter` with `GET /health`; `check_redis()` doing `await client.ping()` under a 1s timeout (any exception → `"unavailable"`, FR-025); `check_spacy_model() -> str` stub returning `"ok"` with a `# TODO: wire real check in Epic 2` comment (FR-026); aggregate to `status` `ok`/`degraded` (FR-024); ALWAYS HTTP 200 (FR-022), schema per [contracts/health.openapi.yaml](contracts/health.openapi.yaml)
- [X] T012 Implement `apps/gateway-api/gateway_api/main.py`: create the FastAPI app, include the health router, and add the `redis_availability_gate` `@app.middleware("http")` that passes through `/health` and returns `JSONResponse(503)` on all other paths when Redis is unavailable (FR-027); also create `apps/gateway-api/gateway_api/__init__.py`
- [X] T013 [P] Create `apps/gateway-api/tests/conftest.py`: pytest fixtures — `httpx.AsyncClient` against the app, an `AsyncMock` Redis-ping patcher, and a valid-`Settings` env fixture
- [X] T014 Implement `apps/gateway-api/tests/test_health.py` with the 5 required cases: (1) `/health` 200 + `ok` when ping succeeds; (2) `/health` 200 + `degraded` when ping raises `ConnectionError`; (3) any non-health route → 503 when Redis unavailable; (4) `Settings()` with invalid `REDIS_ENCRYPTION_KEY` raises `ValueError`; (5) `Settings()` with empty `OPENAI_API_KEY` does NOT raise

**Checkpoint**: `nx run gateway-api:test` is green; `uvicorn gateway_api.main:app` serves `GET /health` returning the documented JSON.

---

## Phase 3: User Story 1 - Launch the entire system with one command (Priority: P1) 🎯 MVP

**Goal**: One `docker compose up` brings all three services to a healthy state with the SPA reachable and Redis private to the network.

**Independent Test**: [quickstart.md](quickstart.md) Scenario A — `docker compose -f docker-compose.yml up` → all three `healthy` < 60s, `/health` 200, SPA on `:3000`, Redis not reachable from host.

### Implementation for User Story 1

- [X] T015 [P] [US1] Create `apps/gateway-api/Dockerfile`: multi-stage — builder installs deps with `uv` and runs `python -m spacy download pl_core_news_lg`; slim Python 3.12 runtime copies only the venv + `gateway_api/`, runs as a non-root user, declares `HEALTHCHECK --start-period=30s` against `/health` (FR-031, FR-033; image size uncapped per R1)
- [X] T016 [P] [US1] Replace `apps/gateway-ui/src/App.tsx` with a minimal placeholder showing "LLM Gateway" and a button that fetches `/api/health` and renders backend status
- [X] T017 [P] [US1] Create `apps/gateway-ui/nginx.conf`: SPA fallback `try_files $uri $uri/ /index.html` and `location /api/ { proxy_pass http://gateway-api:8000/; }` (FR-005)
- [X] T018 [P] [US1] Create `apps/gateway-ui/Dockerfile`: two stages — `node:20-alpine` runs `npm ci && npm run build` → `nginx:1.25-alpine` serves `dist/` with `nginx.conf`
- [X] T019 [US1] Create `docker-compose.yml` (project & network `pw-masters-secure-gateway`): `redis` (`redis:7-alpine`, password `${REDIS_PASSWORD}`, `redis-cli ping` healthcheck, NO host port), `gateway-api` (build `./apps/gateway-api`, `env_file: .env`, `8000:8000`, `curl -f /health` healthcheck, `depends_on redis: service_healthy`), `gateway-ui` (build `./apps/gateway-ui`, `3000:80`, healthcheck returning HTTP 200 on `/` per FR-006, `depends_on gateway-api: service_healthy`) per [contracts/compose-services.md](contracts/compose-services.md)
- [X] T020 [US1] Verify [quickstart.md](quickstart.md) Scenario A end-to-end: build images, `docker compose -f docker-compose.yml up -d`, confirm all healthy < 60s, `/health` 200, SPA loads + health-ping works, `redis-cli -h localhost ping` refused (SC-001, SC-010); record actual `/health` response time against the running stack (real-latency check for SC-002, complementing the mocked check in T028); record built backend image size for reference (R1)

**Checkpoint**: The full stack starts with one command and is demonstrable — MVP complete.

---

## Phase 4: User Story 2 - Develop locally with a fast hot-reload loop (Priority: P2)

**Goal**: Only Redis in Docker; backend and frontend run natively with hot reload; no image rebuilds during development.

**Independent Test**: [quickstart.md](quickstart.md) Scenario B — `docker compose up redis` + `nx run gateway-api:serve` + `nx run gateway-ui:serve`; edits to backend and frontend reload without any image rebuild; default `docker compose up` excludes the UI container.

### Implementation for User Story 2

- [X] T021 [P] [US2] Configure backend targets in `apps/gateway-api/project.json`: `serve` (`uvicorn gateway_api.main:app --reload --port 8000`, cwd `apps/gateway-api`), `test` (`pytest tests/`, cached), `lint` (flake8) per [plan.md](plan.md)
- [X] T022 [P] [US2] Verify the frontend targets generated in `apps/gateway-ui/project.json` — use the default names produced by `@nx/react` + Vite (`serve` = the Vite dev server with HMR, plus `build`, `test` (vitest), `lint`); do not rename them
- [X] T023 [P] [US2] Add the dev proxy to `apps/gateway-ui/vite.config.ts`: `server.proxy` maps `/api` → `http://localhost:8000` with `rewrite: p => p.replace(/^\/api/, '')` (FR-012, research D8)
- [X] T024 [US2] Create `docker-compose.override.yml`: `redis` adds `ports: ["6379:6379"]` (FR-009); `gateway-api` bind-mounts `./apps/gateway-api/gateway_api:/app/gateway_api` and overrides `command` to `uvicorn ... --reload` (FR-010); `gateway-ui` gets `profiles: ["production-only"]` (FR-011) per [contracts/compose-services.md](contracts/compose-services.md)
- [X] T025 [US2] Write `README.md`: prerequisites (Docker, Node 20, Python 3.12, uv), quickstart (`cp .env.example .env` → fill → `docker compose up`), `REDIS_ENCRYPTION_KEY` generation one-liner, the three-terminal dev workflow, an Nx command reference (`nx run gateway-api:serve`, `nx run gateway-ui:serve`, `nx run-many --target=test`), and `/health` verification (FR-015)
- [X] T026 [US2] Verify [quickstart.md](quickstart.md) Scenario B: only-Redis Docker + native serve/dev hot reload confirmed; `docker compose up` (override merged) starts redis + gateway-api only, no `gateway-ui` (SC-005, SC-008)

**Checkpoint**: Developers get a sub-second inner loop; US1 and US2 both work independently.

---

## Phase 5: User Story 3 - Observe health and survive dependency failures (Priority: P3)

**Goal**: Prove and harden the runtime guarantees — health always 200, graceful degradation, fail-fast on bad config, and no secrets in logs.

**Independent Test**: [quickstart.md](quickstart.md) Scenarios C & D — kill Redis → `/health` 200/degraded, non-health 503, no crash, auto-recovery; invalid encryption key → non-zero exit < 5s.

> **Note**: The core behaviors (health aggregation, 503 gate, fail-fast key validation) are implemented and unit-tested in Foundational (T009–T014). This phase adds observability hygiene that no other story requires and validates the guarantees in the orchestrated stack.

### Implementation for User Story 3

- [X] T027 [US3] Add logging hygiene in `apps/gateway-api/gateway_api/main.py` (and a small `logging` setup if needed): emit only operational metadata (status, timings, error categories); guarantee `REDIS_ENCRYPTION_KEY`, `REDIS_PASSWORD`, and API keys are never logged or echoed in error/health bodies (FR-030)
- [X] T028 [P] [US3] Add `apps/gateway-api/tests/test_observability.py`: assert no secret value appears in captured logs during startup/requests, and a sanity check that `/health` responds well under 500ms with a mocked Redis (SC-002, FR-030)
- [X] T029 [US3] Validate [quickstart.md](quickstart.md) Scenario C against the running stack: stop `redis` → `/health` stays 200 + `degraded`, a non-health route returns 503, `gateway-api` stays Up (no crash), and restarting `redis` returns `/health` to `ok` with no backend restart (SC-004)
- [X] T030 [US3] Validate [quickstart.md](quickstart.md) Scenario D: starting the backend with an invalid `REDIS_ENCRYPTION_KEY` exits non-zero within 5s before binding a port; empty `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` produce no startup error (SC-003, FR-019, FR-020)

**Checkpoint**: All runtime guarantees demonstrably hold; all three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup spanning the whole stack.

- [X] T031 [P] Run [quickstart.md](quickstart.md) Scenario F: `nx run-many --target=test` runs pytest (gateway-api) + vitest (gateway-ui), both green (SC-007)
- [X] T032 [P] Record the measured backend image size in `README.md` (reference only — R1, no gate)
- [X] T033 Remove `@nx/react` generator boilerplate not used by the placeholder UI and confirm `git status` shows no `.env` tracked (SC-009)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories** (the backend must exist before it can be packaged, served, or validated).
- **US1 (Phase 3)**: Depends on Foundational. This is the post-foundation MVP.
- **US2 (Phase 4)**: Depends on Foundational. `T024` (override) extends `T019`'s base compose, so US2 is best done after US1's `docker-compose.yml` exists (or in parallel by a second developer who coordinates the compose files).
- **US3 (Phase 5)**: Depends on Foundational; Scenarios C/D in `T029`/`T030` exercise the running stack, so they are easiest to run after US1's compose (`T019`/`T020`).
- **Polish (Phase 6)**: After all desired stories.

### Cross-story note (infrastructure epic)

The spec's US3 is a quality guarantee whose *implementation* (the `/health` endpoint + 503 gate + fail-fast) is shared by every story, so it lives in Foundational. Consequently US1 is buildable immediately after Foundational (no dependency on a later story), and US3's phase is hygiene + end-to-end validation. This is the one intentional deviation from "each story is 100% self-contained."

### Within Each Story / Phase

- Foundational: T008 → T009 → T010 → T011 → T012, then T013 [P] / T014 (tests last).
- US1: T015/T016/T017/T018 [P] → T019 (needs the two Dockerfiles) → T020 (verify).
- US2: T021/T022/T023 [P] → T024 → T025 → T026 (verify).
- US3: T027 → T028 [P] → T029 → T030.

### Parallel Opportunities

- Setup: T003 & T004 (different project dirs) in parallel after T002; T006 & T007 in parallel.
- Foundational: T013 can proceed alongside T011/T012 once T009 exists.
- US1: all four file-creation tasks T015–T018 in parallel.
- US2: T021, T022, T023 in parallel (three different files).
- US3: T028 in parallel with T027's manual verification prep.
- Polish: T031 & T032 in parallel.

---

## Parallel Example: User Story 1

```bash
# After Foundational is green, launch all US1 artifact tasks together:
Task: "T015 Backend Dockerfile in apps/gateway-api/Dockerfile"
Task: "T016 Placeholder App.tsx in apps/gateway-ui/src/App.tsx"
Task: "T017 nginx.conf in apps/gateway-ui/nginx.conf"
Task: "T018 Frontend Dockerfile in apps/gateway-ui/Dockerfile"
# Then converge:
Task: "T019 docker-compose.yml at repo root"
```

---

## Implementation Strategy

### MVP First (Setup → Foundational → US1)

1. Phase 1 Setup → workspace + both projects scaffolded.
2. Phase 2 Foundational → backend core green under `nx run gateway-api:test`.
3. Phase 3 US1 → `docker compose up` brings the full stack healthy.
4. **STOP & VALIDATE**: quickstart Scenario A. This is a demonstrable MVP.

### Incremental Delivery

- Foundation + US1 → one-command stack (MVP, demo-ready).
- + US2 → fast local dev loop.
- + US3 → proven resilience + logging hygiene.
- Polish → full `nx run-many --target=test` green + cleanup.

### Parallel Team Strategy

After Foundational: Developer A takes US1 (packaging/compose), Developer B takes US2 (dev ergonomics) coordinating on the two compose files, Developer C takes US3 (hygiene + validation) once US1's compose lands.

---

## Notes

- `[P]` = different files, no incomplete dependencies.
- `[Story]` labels (US1/US2/US3) appear only in Phases 3–5; Setup/Foundational/Polish have none.
- Backend unit tests accompany the Foundational code; US3 adds an observability test (`test_observability.py`).
- Image size is uncapped (R1 resolved) — record it, don't gate on it.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
