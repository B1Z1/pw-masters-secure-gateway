# Phase 1 Data Model: Infrastructure and Runtime Environment

**Feature**: 001-infrastructure-runtime | **Date**: 2026-06-15

This epic provisions runtime and configuration rather than persistent domain data. The "entities" below are configuration and runtime-state structures, not database tables. Field-level contracts for the wire formats live in [contracts/](contracts/).

---

## Entity: Settings (application configuration)

The single configuration object, loaded once at startup from environment variables via `pydantic-settings`. Drives every other component.

| Field | Type | Required | Default | Validation |
|---|---|---|---|---|
| `redis_url` | `str \| None` | No | `None` | If absent/empty → backend boots but all non-`/health` routes return 503 (FR-027/edge case). |
| `redis_password` | `str` | Yes | — | Used to compose/authenticate the Redis connection; never logged (FR-030). |
| `redis_encryption_key` | `str` | **Yes** | — | **MUST be valid base64 decoding to exactly 32 bytes**, else `ValueError` at instantiation → non-zero exit (FR-019, SC-003). AES-256 key material. |
| `redis_session_ttl` | `int` | No | `3600` | Seconds; session lifetime for Epic 3. Positive integer. |
| `openai_api_key` | `str \| None` | No | `None` | Optional; no startup validation (FR-020). Error only on first use (Epic 5). |
| `anthropic_api_key` | `str \| None` | No | `None` | Optional; no startup validation (FR-020). |
| `ollama_base_url` | `str` | No | `http://host.docker.internal:11434` | Reachability environment-dependent on Linux (research R2). |
| `default_llm_provider` | `str` | No | `openai` | One of the supported providers; not validated for reachability this epic. |
| `default_model` | `str` | No | `gpt-4o` | Free-form model id; consumed in Epic 5. |

**Lifecycle**: instantiated once at process start. Invalid `redis_encryption_key` aborts startup before any request is served. The full variable contract (with inline-doc requirements and the `.env.example` shape) is in [contracts/environment.md](contracts/environment.md).

**Invariants**:
- Secret fields (`redis_password`, `redis_encryption_key`, API keys) MUST NOT appear in logs, error messages, or the health response.
- No field beyond `redis_encryption_key` blocks startup.

---

## Entity: Service (deployable runtime unit)

A unit in the Compose topology. Three instances this epic. Not persisted — describes the orchestration contract (full detail in [contracts/compose-services.md](contracts/compose-services.md)).

| Field | `gateway-api` | `gateway-ui` | `redis` |
|---|---|---|---|
| Internal network name | `gateway-api` | `gateway-ui` | `redis` |
| Network | `pw-masters-secure-gateway` (internal) | same | same |
| Host-published port | `8000` | `3000:80` | **none in prod**; `6379:6379` only in dev override |
| Health signal | `GET /health` 200 | nginx serving (HTTP 200 on `/`) | `redis-cli ping` → PONG |
| Starts after (prod) | `redis` healthy | `gateway-api` healthy | — (starts first) |
| Build context | `apps/gateway-api` (multi-stage) | `apps/gateway-ui` (node→nginx) | image `redis:7-alpine` |

**State / startup ordering** (FR-004): `redis (healthy) → gateway-api (healthy) → gateway-ui`. Enforced by `depends_on … condition: service_healthy`.

**Dev-mode variance** (override, FR-008–FR-013): `redis` gains host port `6379`; `gateway-api` mounts source + runs `uvicorn --reload`; `gateway-ui` is assigned the `production-only` profile and therefore excluded from the default `docker compose up`.

---

## Entity: HealthStatusReport (response payload)

The structured result of `GET /health`. Computed per request; never stored. Schema contract in [contracts/health.openapi.yaml](contracts/health.openapi.yaml).

| Field | Type | Values | Rule |
|---|---|---|---|
| `status` | `str` (enum) | `"ok"` \| `"degraded"` | Aggregation: `"degraded"` if **any** dependency is `"unavailable"`, else `"ok"` (FR-024). |
| `dependencies` | object | map of name → status | One entry per tracked dependency. |
| `dependencies.redis` | `str` (enum) | `"ok"` \| `"unavailable"` | From `await client.ping()` within 1s; any exception/timeout → `"unavailable"` (FR-025). |
| `dependencies.spacy_model` | `str` (enum) | `"ok"` \| `"unavailable"` | Epic 1: stub always `"ok"` (FR-026, research D7). Epic 2 may return `"unavailable"`. |

**HTTP status**: ALWAYS `200`, even when `status` is `"degraded"` (FR-022). Distinct from the non-health gate, which returns `503` when Redis is unavailable.

**Example — all healthy**
```json
{ "status": "ok", "dependencies": { "redis": "ok", "spacy_model": "ok" } }
```
**Example — Redis down**
```json
{ "status": "degraded", "dependencies": { "redis": "unavailable", "spacy_model": "ok" } }
```

---

## Entity: RedisClient (runtime dependency handle)

A process-singleton async client; not data, but a runtime-state holder with defined failure semantics (research D4).

| Aspect | Behavior |
|---|---|
| Construction | Lazy, from `redis_url`; **never raises** on bad/missing URL. |
| Liveness | `await ping()` bounded to 1s; failure classified as `"unavailable"`, not propagated as a 500. |
| Crash safety | A Redis outage at runtime MUST NOT crash the process (FR-028). |
| Recovery | Re-evaluated per request → automatic recovery when Redis returns (no restart). |
| Future use | Encrypted session/mapping storage in Epic 3 (out of scope here). |

---

## Relationships

```text
Settings ──drives──▶ RedisClient (built from redis_url + redis_password)
Settings ──validates at startup──▶ redis_encryption_key (32 bytes, AES-256)
RedisClient ──liveness feeds──▶ HealthStatusReport.dependencies.redis
check_spacy_model() (stub) ──feeds──▶ HealthStatusReport.dependencies.spacy_model
HealthStatusReport ──aggregates──▶ status (ok | degraded)
Service[redis].health ──gates──▶ Service[gateway-api].start ──gates──▶ Service[gateway-ui].start
RedisClient.liveness ──gates──▶ non-/health routes (503 when unavailable)
```

No persistent schema, migrations, or domain records are created in this epic.
