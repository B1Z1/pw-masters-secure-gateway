# Contract: Environment Configuration (`.env`)

**Feature**: 001-infrastructure-runtime | Implements F-02 / FR-016–FR-021

The backend reads **all** configuration from environment variables (via `pydantic-settings`). The repository ships `.env.example` with every variable documented inline; the real `.env` is git-ignored and never committed.

## Variable contract

| Variable | Required | Example / default | Startup validation | Consumed by |
|---|---|---|---|---|
| `REDIS_URL` | optional* | `redis://:changeme@redis:6379/0` | none | Redis client (D4). *Absent → 503 on non-health routes. |
| `REDIS_PASSWORD` | **yes** | `changeme` | none (presence assumed) | Redis auth; Compose `redis` service |
| `REDIS_ENCRYPTION_KEY` | **yes** | (generated, see below) | **base64 → exactly 32 bytes, else `ValueError` → non-zero exit** | AES-256 mapping store (Epic 3) |
| `REDIS_SESSION_TTL` | optional | `3600` | positive int | Session TTL (Epic 3) |
| `OPENAI_API_KEY` | optional | _(empty)_ | **none** (FR-020) | OpenAI adapter (Epic 5) |
| `ANTHROPIC_API_KEY` | optional | _(empty)_ | **none** (FR-020) | Anthropic adapter (Epic 5) |
| `OLLAMA_BASE_URL` | optional | `http://host.docker.internal:11434` | none | Ollama adapter (Epic 5); Linux caveat R2 |
| `DEFAULT_LLM_PROVIDER` | optional | `openai` | none | Provider router (Epic 5) |
| `DEFAULT_MODEL` | optional | `gpt-4o` | none | Provider router (Epic 5) |

\* Optional to *start* the process, but its absence degrades the system to health-only (503 elsewhere).

## `.env.example` shape (committed, documented inline)

```dotenv
# --- Redis (session & encrypted mapping store) ---
# Connection URL. Format: redis://:<password>@<host>:<port>/<db>
# In the Docker stack the host is the service name `redis`.
REDIS_URL=redis://:changeme@redis:6379/0

# Must match the password embedded in REDIS_URL and the redis service.
REDIS_PASSWORD=changeme

# AES-256 key. MUST be base64 that decodes to EXACTLY 32 bytes.
# Generate with:
#   python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
REDIS_ENCRYPTION_KEY=

# Session lifetime in seconds (mapping TTL). Default: 3600 (1h).
REDIS_SESSION_TTL=3600

# --- LLM providers (all optional at startup; error only on first use) ---
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
# On native Linux Docker, host.docker.internal may need:
#   extra_hosts: ["host.docker.internal:host-gateway"]  (added in Epic 5)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# --- Defaults ---
DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
```

## Behavioral contract (validation)

| Condition | Required behavior |
|---|---|
| `REDIS_ENCRYPTION_KEY` valid (base64 → 32 bytes) | Startup proceeds. |
| `REDIS_ENCRYPTION_KEY` not base64, or ≠ 32 bytes after decode | `ValueError` at `Settings()` instantiation → uvicorn exits non-zero within 5s (SC-003). |
| `REDIS_URL` missing | Backend boots; `/health` reports `redis: unavailable` (`degraded`); all non-health routes → 503. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` empty | No startup error; failure deferred to first provider use (Epic 5). |
| Any secret value | MUST NOT be logged or echoed in `/health` or error bodies (FR-030). |

## Git hygiene contract

- `.env` MUST be listed in `.gitignore` and never committed (SC-009).
- `.env.example` MUST contain only placeholders — never a real key, password, or API token.
