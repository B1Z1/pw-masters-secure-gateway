# Optional local Ollama backend (dev / demo)

An **opt-in** way to run a self-hosted LLM (Ollama) alongside the gateway for the
Epic 4 chat round-trip. It is **not** part of the production stack.

## Why this is separate

The gateway is provider-agnostic (Constitution IV): the LLM backend is a
dependency you point at via `OLLAMA_BASE_URL`, not something the core stack owns.

- **Production** → the operator points the gateway at a hosted API
  (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) or at their own model server. Nothing
  here is required.
- **Local dev / demo** → use this folder to stand up a containerized Ollama with
  one extra compose file, so the whole thing runs self-contained.

The core `docker-compose.yml` stays LLM-agnostic; this file only adds an
in-network `ollama` service and overrides `OLLAMA_BASE_URL` for the gateway.

## Three ways the gateway reaches Ollama (same `.env`, one env var)

| Mode | How you run | `OLLAMA_BASE_URL` |
|------|-------------|-------------------|
| Native dev (uvicorn on host) | `uv run uvicorn …` + `ollama serve` on host | `http://localhost:11434` |
| Core compose, **host** Ollama | `docker compose up` + `ollama serve` on host | `http://host.docker.internal:11434` (the `.env` default) |
| Core compose **+ this add-on** | the command below | `http://ollama:11434` (set by this file) |

## Run it

```bash
# from the repo root, with a valid .env (REDIS_* etc.):
docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d

# pull the model the gateway will use (reads DEFAULT_MODEL from .env, or pass one;
# the "ollama/" prefix is stripped automatically before `ollama pull`):
dev/ollama/pull-model.sh            # or: dev/ollama/pull-model.sh ollama/llama3

# set DEFAULT_MODEL in .env to that model WITH the "ollama/" prefix (Epic 5 routes by
# prefix: ollama/<name> -> Ollama; a bare name -> 400 unknown model), e.g.
# DEFAULT_MODEL=ollama/qwen2.5:3b. Then exercise the chat endpoint (no model field =
# use the default), or send "model": "ollama/qwen2.5:3b" explicitly:
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Streść umowę: najemca Jan Kowalski z Krakowa."}]}' | jq
```

## Behind a TLS-inspecting proxy (e.g. Netskope)

If your network intercepts TLS, Ollama cannot pull models (`x509: certificate
signed by unknown authority`). Ollama is a Go binary, so point it at a CA the
proxy's root signs — two env vars (default no-op, so direct internet is unaffected):

```bash
OLLAMA_CA_FILE=~/.certs/netskope-ca.pem \
OLLAMA_SSL_CERT_FILE=/etc/ssl/proxy-ca.pem \
  docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d ollama
# then pull as usual:
dev/ollama/pull-model.sh
```

`OLLAMA_CA_FILE` is the host CA bundle (bind-mounted to `/etc/ssl/proxy-ca.pem`);
`OLLAMA_SSL_CERT_FILE` is that in-container path. The gateway↔Ollama hop is plain
in-network HTTP, so only model pulls need this.

## Notes & caveats

- **macOS**: Docker has no GPU (Metal) access, so the container runs **CPU-only**
  and is slow. For a fast demo on a Mac, run Ollama **natively** on the host and
  use the core compose with the default `host.docker.internal` URL instead.
- **Linux + NVIDIA GPU**: uncomment the `deploy.resources.reservations.devices`
  block in `docker-compose.ollama.yml` for hardware acceleration.
- **Models are large** (GBs). They are kept in the `ollama-models` named volume,
  so you only download each once.
- `DEFAULT_MODEL` must be an **`ollama/`-prefixed installed** model (e.g.
  `ollama/qwen2.5:3b`); the router strips the prefix before calling Ollama. A bare
  name → **400** (unknown model); a prefixed-but-not-pulled model → **503** (missing
  model). Timeouts (tune `OLLAMA_TIMEOUT`) return **504**.
