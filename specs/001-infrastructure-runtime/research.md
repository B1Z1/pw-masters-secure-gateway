# Phase 0 Research: Infrastructure and Runtime Environment

**Feature**: 001-infrastructure-runtime | **Date**: 2026-06-15

This document resolves the open technical decisions for Epic 1 and records the risks that the implementation must actively measure. Each decision lists what was chosen, why, and the alternatives rejected.

---

## D1 — Scaffolding Nx into an existing, non-empty repository

**Decision**: Scaffold the Nx workspace **in place** at the repo root, not via `create-nx-workspace <name>` (which creates a nested sub-directory).

**Context**: The repository is already initialized and non-empty — it contains `.git/`, `.specify/`, `.claude/`, `docs/`, `specs/`, `CLAUDE.md`, `README.md`. `npx create-nx-workspace@latest pw-masters-secure-gateway …` would create `./pw-masters-secure-gateway/` and nest the whole workspace one level down, breaking every path in this plan and the Spec Kit tooling.

**Approach (chosen by maintainer — subfolder, then move up)**:
1. Run `create-nx-workspace@latest pw-masters-secure-gateway --preset=apps --packageManager=npm --nxCloud=skip` so it generates a clean workspace into a **temporary subfolder** (e.g. `./_nx-bootstrap/pw-masters-secure-gateway/` or any scratch path outside the repo root).
2. Move the generated workspace files up to the repo root — `nx.json`, `package.json`, `package-lock.json`, `tsconfig.base.json`, `.nx/`, and `apps/` (if the preset created any) — preserving the existing `.git/`, `docs/`, `specs/`, `.specify/`, `.claude/`, `CLAUDE.md`. Remove the now-empty scratch subfolder.
3. Merge (do not overwrite) the generated `.gitignore` with project-specific entries (`.env`, `.nx/cache`, `dist/`, `node_modules/`, `.venv/`, `__pycache__/`).
4. Keep the existing `README.md`; replace its body in Phase 5.
5. Verify with `nx show projects` (empty list is fine before generators run) and `nx graph`.

**Rationale**: Preserves git history and the already-present Spec Kit + docs scaffolding; yields the exact root layout the spec's monorepo structure requires. Generating in a subfolder sidesteps `create-nx-workspace`'s refusal to run in a non-empty directory.

**Alternatives rejected**:
- *Nested `create-nx-workspace` left in place*: breaks all documented paths and the single-`docker compose up`-from-root requirement.
- *`nx init` in-place*: viable but yields a less canonical `apps`-preset layout; the subfolder-then-move path gives the standard workspace structure verbatim.
- *Move the repo into a fresh workspace*: loses `.git` lineage and re-creates `.specify` state.

---

## D2 — Nx task caching configuration

**Decision**: Configure caching via `targetDefaults` in `nx.json` with `"cache": true` on `build`, `test`, and `lint`. Leave the dev-server targets — `serve` on **both** backend (uvicorn) and frontend (the generated Vite `serve`) — **uncached** (long-running processes).

```jsonc
// nx.json (excerpt)
{
  "targetDefaults": {
    "build": { "cache": true },
    "test":  { "cache": true, "inputs": ["default", "^default"] },
    "lint":  { "cache": true }
  }
}
```

**Rationale**: `targetDefaults` is the Nx 19+ idiom; the legacy `tasksRunnerOptions.cacheableOperations` array is deprecated. Long-running dev servers must never be cached.

**Alternatives rejected**: Legacy `cacheableOperations` (still works but deprecated; avoid carrying forward tech debt on a greenfield project).

**Note**: The spec prompt's `project.json` used `@nxlv/python:run-commands` for `serve`/`test`. The built-in `nx:run-commands` executor is equally valid and avoids coupling to a specific `@nxlv/python` version. Decision: use whichever the installed `@nxlv/python` exposes; if its run-commands executor is absent, fall back to `nx:run-commands`. Functionally identical for `uvicorn …` / `pytest tests/`.

---

## D3 — Backend dependency & runtime toolchain (uv + multi-stage)

**Decision**: Manage Python deps with `uv` (per `@nxlv/python` uv-project). Build a multi-stage image: **stage 1 (builder)** installs deps into a virtualenv and runs `python -m spacy download pl_core_news_lg`; **stage 2 (runtime)** is a slim Python 3.12 base that copies only the venv + app code, runs as a non-root user, and declares a `HEALTHCHECK` against `/health` with `--start-period=30s`.

**Rationale**: uv is native to the chosen plugin, fast, and lockfile-reproducible. Multi-stage keeps build tooling out of the runtime image. `--start-period` absorbs interpreter + (future) model load time so the orchestrator does not flap the container during boot.

**Alternatives rejected**: pip + single-stage (larger image, build tooling shipped to runtime); Poetry (the plugin's uv-project path was explicitly chosen).

---

## D4 — Redis client lifecycle & failure semantics

**Decision**: Create a module-level **async** `redis.Redis` client from `REDIS_URL` in `dependencies.py`, exposed via `get_redis_client()`. Construction is lazy and MUST NOT raise on a bad/missing URL — only actual operations (`ping`, `get`, `set`) fail. The health check wraps `await client.ping()` in a 1-second timeout and treats **any** exception (connection error, timeout, auth failure, missing URL) as `"unavailable"`.

**Rationale**: Satisfies FR-025/FR-028 (graceful degradation, never crash) and the edge case where `REDIS_URL` is missing (backend still boots, `/health` still answers). Per-request re-evaluation gives automatic recovery when Redis returns (Assumption: health recovery is per-request).

**Alternatives rejected**: Eager connect at startup (would crash the process on a transient Redis outage, violating FR-028); sync client (FastAPI is async; would block the event loop).

---

## D5 — Encryption-key validation placement (fail-fast)

**Decision**: Validate `REDIS_ENCRYPTION_KEY` inside the `pydantic-settings` `Settings` model with a field validator: base64-decode and assert the result is exactly 32 bytes, else raise `ValueError`. Because `Settings()` is instantiated at import/startup, an invalid key raises before the app serves traffic, and uvicorn exits non-zero.

**Rationale**: Centralizes the security-critical check at the single config boundary; fail-fast (Constitution III, FR-019, SC-003 < 5s). 32 bytes = AES-256 key material for the Epic 3 mapping store.

**LLM keys**: `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` are `Optional[str] = None` with **no** startup validation (FR-020) — a missing key surfaces only when that provider is first used (Epic 5).

**Alternatives rejected**: Validating in `main.py` startup hook (later, less centralized, easy to bypass in tests); validating lazily on first Redis write (would let a misconfigured-encryption server accept traffic — strictly worse).

---

## D6 — Non-health request gating (middleware)

**Decision**: A single FastAPI `@app.middleware("http")` (`redis_availability_gate`) checks `request.url.path`; for `/health` it passes through untouched, otherwise it verifies Redis availability and returns `JSONResponse(status_code=503, …)` when unavailable.

**Rationale**: One choke point implements FR-027 (503 on non-health when Redis down) while keeping `/health` always reachable (FR-022). Centralizing in middleware means individual routers (added in later epics) inherit the gate for free.

**Performance note**: `/health` is exempt from this gate, so the middleware's Redis check does not affect health latency (SC-002). For non-health routes, a bounded ping (≤1s) per request is sufficient for this epic; a short-TTL liveness cache is an **optional** optimization, not required here. The binding contract is simply: non-health routes return 503 when Redis is unavailable.

**Alternatives rejected**: Per-router dependency injection (repetition, easy to forget on a new router); exact-path allowlist beyond `/health` (none needed this epic).

---

## D7 — SpaCy health check stub (Epic 2 seam)

**Decision**: `health.py` defines `def check_spacy_model() -> str: return "ok"` with a `# TODO: wire real check in Epic 2 (NER engine)` comment. The health aggregator calls it like any other dependency check. Epic 2 replaces **only the function body** (load/verify `pl_core_news_lg`) without touching the endpoint, the aggregation rule, or the response schema.

**Rationale**: Constitution IX (simplicity; documented stub) and FR-026 (structured so Epic 2 swaps it in cleanly). The product backlog's F-03 already anticipates a real `"spacy_model": "unavailable"` path — the stub's signature matches so that future state slots into the existing `dependencies` map.

**Alternatives rejected**: Loading the model in Epic 1 just to report health (couples this epic to NER, adds startup latency, and worsens Risk R1).

---

## D8 — Frontend dev proxy vs. nginx prod proxy (two API paths)

**Decision**: Two distinct proxy configurations for the two run modes:
- **Dev (Vite)**: `vite.config.ts` `server.proxy` maps `/api` → `http://localhost:8000`, rewriting `^/api` → `` so the natively-running backend (no `/api` prefix) receives clean paths.
- **Prod (nginx)**: `nginx.conf` serves the built SPA with `try_files $uri $uri/ /index.html` (SPA fallback) and proxies `/api/` → `http://gateway-api:8000/` over the Docker network.

**Rationale**: The frontend always calls `/api/...`; each environment routes that prefix to the right backend without app-code changes. Satisfies FR-005 (SPA fallback + API forwarding) and FR-012 (dev proxy to native backend).

**Alternatives rejected**: Hard-coding absolute backend URLs in the SPA (breaks portability between dev/prod and leaks ports into client code); CORS-only with no proxy (more moving parts, no SPA-fallback benefit).

---

## R1 — RESOLVED: backend image size budget relaxed

**Original tension**: SC-006 / FR-032 originally capped the backend runtime image at **< 500MB**, while FR-033 + Constitution VI require baking the Polish SpaCy model `pl_core_news_lg` into the image at build time. Large SpaCy `*_lg` models ship full word vectors and are frequently **~500MB on their own**, making a sub-500MB total image effectively infeasible.

**Decision (maintainer, 2026-06-15)**: **Relax the budget — image size does not matter.** The Polish model is baked into the image unconditionally (honoring Polish First + FR-033 + the single-build-artifact intent). FR-032 and SC-006 are amended: no hard size cap; multi-stage build is retained only for hygiene (keep build tooling out of the runtime stage), and the final size is **recorded for reference**, not gated.

**Implications**:
- No slimming work is required to hit a numeric target; standard multi-stage hygiene is sufficient.
- The model is **not** deferred to Epic 2 — it ships in the Epic 1 backend image.
- The Dockerfile task's acceptance is "image builds and `/health` is reachable", with image size logged for the thesis's reproducibility notes.

**Status**: RESOLVED. Spec (FR-032, SC-006), plan, and contracts updated accordingly.

---

## R2 — RISK: `host.docker.internal` on Linux (Ollama base URL)

**Risk**: `OLLAMA_BASE_URL=http://host.docker.internal:11434` resolves automatically on Docker Desktop (macOS/Windows) but **not** on native Linux Docker by default.

**Resolution**: Not exercised in Epic 1 (no LLM calls). Documented as an environment-dependent limitation (spec Assumptions). When Epic 5 needs it on Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` to the `gateway-api` service. No action required this epic beyond noting it in the README.

**Status**: Deferred to Epic 5; noted.

---

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| How to add Nx to an existing repo without nesting | D1 — generate in a temp subfolder, then move files up to root, preserve `.git` |
| Caching config idiom | D2 — `targetDefaults` cache for build/test/lint |
| Python toolchain & image strategy | D3 — uv + multi-stage, non-root, `--start-period=30s` |
| Redis failure behavior | D4 — lazy async client, never crash, 1s ping timeout |
| Where to validate the AES key | D5 — `pydantic-settings` validator, fail-fast at import |
| How to gate non-health routes | D6 — single `http` middleware exempting `/health` |
| SpaCy check for Epic 1 | D7 — stub `check_spacy_model()`, Epic 2 swaps body |
| Dev vs prod API routing | D8 — Vite proxy (dev) + nginx proxy & SPA fallback (prod) |
| Image-size feasibility | **R1 — RESOLVED: budget relaxed, model baked in** |
| Linux `host.docker.internal` | R2 — deferred to Epic 5, documented |
