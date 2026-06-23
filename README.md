# LLM Anonymization Gateway

A secure gateway that sits between users and external LLM providers: it detects
personally identifiable information (PII) in requests, substitutes realistic
synthetic data before sending to the provider, and restores the original values
in the response. Master's thesis project — use case: Polish civil-law contracts.

## Prerequisites

- Docker + Docker Compose v2
- Node 20 and npm
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Nx via `npx nx` (installed with the workspace)

## Quickstart (full stack)

```bash
cp .env.example .env
# Generate a valid 32-byte AES key and paste it into REDIS_ENCRYPTION_KEY:
python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# Edit .env: set REDIS_ENCRYPTION_KEY (and REDIS_PASSWORD if changed).

npm run docker:stack     # build + start all three services (detached)
npm run docker:ps        # all three healthy within ~60s
curl -s localhost:8000/health   # {"status":"ok",...}
open http://localhost:3000      # SPA: "LLM Gateway" + health-ping button
npm run docker:down      # stop & remove
```

`REDIS_ENCRYPTION_KEY` must be base64 decoding to **exactly 32 bytes**, or the
backend fails fast (non-zero exit) before binding a port.

### npm scripts (whole stack)

| Script | Command |
|---|---|
| `npm run docker:stack` | `up --build -d` — build images + start all three services |
| `npm run docker:build` | build images only |
| `npm run docker:up` | start (no rebuild) |
| `npm run docker:down` | stop & remove |
| `npm run docker:logs` | follow logs |
| `npm run docker:ps` | service status |

### Building behind a corporate TLS-inspecting proxy

If image builds fail with `invalid peer certificate: UnknownIssuer`, your network
runs a TLS-inspecting proxy (e.g. Netskope/Zscaler) whose CA the build container
doesn't trust. Export your corporate CA bundle and point `CA_CERT_FILE` at it —
it is injected **only at build time** as a Docker secret and never lands in the
runtime images:

```bash
# Export the corporate root CA from the macOS keychain (one-off):
security find-certificate -a -p /Library/Keychains/System.keychain \
  | … > corp-ca.pem      # keep the CA cert(s) for your proxy

CA_CERT_FILE=$(pwd)/corp-ca.pem npm run docker:stack
# or: CA_CERT_FILE=$(pwd)/corp-ca.pem docker compose -f docker-compose.yml build
```

With no `CA_CERT_FILE`, the build uses an empty placeholder (`.docker/empty.crt`)
and behaves as a normal build — correct on networks without such a proxy.

## Local hot-reload dev workflow (three terminals)

`docker compose up` (override auto-merged) starts **redis + gateway-api** only —
the UI is held back by its `production-only` profile so you run Vite natively.

```bash
# Terminal 1 — only Redis (override exposes 6379 on the host)
docker compose up redis

# Terminal 2 — native backend with hot reload (uvicorn --reload on :8000)
nx run gateway-api:serve

# Terminal 3 — native frontend with HMR (Vite dev server on :4200; /api → :8000)
nx run gateway-ui:serve
```

**Native backend → dockerized Redis:** when the backend runs natively but Redis
runs in Docker, set the host to `localhost` in your `.env` (the `redis` hostname
only resolves inside the Docker network):

```dotenv
REDIS_URL=redis://:changeme@localhost:6379/0
```

Otherwise `/health` reports `redis: unavailable` (the override exposes Redis on
host port 6379 specifically for this).

## Nx command reference

| Command | What it does |
|---|---|
| `nx run gateway-api:serve` | uvicorn `--reload` on :8000 |
| `nx run gateway-ui:serve` | Vite dev server (HMR) on :4200, proxies `/api` → :8000 |
| `nx run gateway-api:test` | pytest (backend) |
| `nx run gateway-ui:test` | vitest (frontend) |
| `nx run-many --target=test` | both suites |
| `nx build gateway-ui` | production SPA bundle → `apps/gateway-ui/dist` |
| `nx run gateway-api:lint` | ruff (backend) |

## Health verification

`GET /health` always returns HTTP 200 and reports per-dependency status:

```json
{ "status": "ok", "dependencies": { "redis": "ok", "spacy_model": "ok" } }
```

When Redis is down it reports `"status": "degraded"` (still HTTP 200), and every
**non-health** route returns 503 until Redis recovers — the process never crashes.

## Notes & limitations

- **Backend image size** is uncapped — the Polish SpaCy model `pl_core_news_lg`
  is baked into the image at build time (R1 resolved). Measured for reference
  (not gated): `gateway-api` ≈ **1.86 GB**, `gateway-ui` ≈ **76 MB**.
- **Frontend Docker build context** is the repository root (not `apps/gateway-ui`)
  because an Nx build needs the workspace root; see `apps/gateway-ui/Dockerfile`.
- **Linting** uses `ruff` (the `@nxlv/python` default), which covers the pyflakes/
  pycodestyle rules the plan referred to as "flake8".
- **uv behind a TLS-inspecting proxy**: if `uv sync` reports an unknown issuer
  certificate, add `--system-certs` (uses the OS trust store).
- **`host.docker.internal` on native Linux** (Ollama, Epic 5) may need
  `extra_hosts: ["host.docker.internal:host-gateway"]` on `gateway-api`.
