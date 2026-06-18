---
paths:
  - "dev/ollama/**"
  - "apps/gateway-api/gateway_api/llm_providers/**"
  - "docker-compose*.yml"
  - "**/docker-compose*.yml"
---

# Running a local LLM (Ollama) for this repo

The gateway is provider-agnostic: the LLM backend is pointed at by configuration
(`OLLAMA_BASE_URL`), never owned by the core stack. The core `docker-compose.yml`
contains **no** model server. A self-hosted Ollama is an **opt-in** add-on at
`dev/ollama/` (see [research D11](../../specs/005-anonymization-pipeline/research.md)).
Follow this exact procedure — it encodes gotchas hit during Epic 4 bring-up.

## 1. Bring up the add-on (additive compose)

```bash
docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d ollama gateway-api
```

This is **additive** to the core stack (same project name + network). The `ollama`
service is in-network only; the gateway reaches it at `http://ollama:11434` (the
add-on sets this override automatically).

## 2. Behind a TLS-inspecting proxy (Netskope) — REQUIRED here

Model pulls go to `registry.ollama.ai` over HTTPS and **fail** with
`x509: certificate signed by unknown authority` unless Ollama trusts the proxy CA.
Ollama is a Go binary, so pass the CA via two env vars (default no-op):

```bash
OLLAMA_CA_FILE=~/.certs/netskope-ca.pem \
OLLAMA_SSL_CERT_FILE=/etc/ssl/proxy-ca.pem \
  docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d ollama
```

(The gateway↔Ollama hop is plain in-network HTTP — only model *pulls* need this.)

## 3. Pull a model and set DEFAULT_MODEL

```bash
dev/ollama/pull-model.sh                # pulls DEFAULT_MODEL from .env
# or explicitly:
docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml exec ollama ollama pull qwen2.5:3b
```

Set `DEFAULT_MODEL` in `.env` to an **`ollama/`-prefixed installed** model
(default: `ollama/qwen2.5:3b`). Epic 5 routes by the model **prefix**, so the model
NAME in the request/`DEFAULT_MODEL` must carry `ollama/` — a bare `qwen2.5:3b` now
returns **400 unknown model**, and the router strips the prefix before calling
Ollama (`ollama/qwen2.5:3b` → Ollama sees `qwen2.5:3b`). An installed model whose
prefixed name is sent but isn't pulled → **503 missing_model**. Model
recommendations: `ollama/qwen2.5:3b` follows instructions well in Polish;
`ollama/llama3.2:1b` is faster but too weak to echo names reliably. The chat request
may also override per call with an optional `"model"` field (also `ollama/`-prefixed
for Ollama; `gpt-…`/`claude-…` route to OpenAI/Anthropic instead).

## 4. After changing backend CODE, REBUILD the image

`apps/gateway-api` runs from a **baked image**, not a bind mount. New routes/code
do NOT appear until you rebuild — a stale image returns **404** for new endpoints.
The build installs deps + the spaCy model through the proxy, so pass the build CA:

```bash
CA_CERT_FILE=~/.certs/netskope-ca.pem \
  docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml build gateway-api
docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d gateway-api
```

## `OLLAMA_BASE_URL` per run mode (one env, three values)

| Mode | `OLLAMA_BASE_URL` |
|------|-------------------|
| Native dev (uvicorn on host) + host Ollama | `http://localhost:11434` |
| Core compose + **host** Ollama | `http://host.docker.internal:11434` (the `.env` default) |
| Core compose + the `dev/ollama/` add-on | `http://ollama:11434` (set by the add-on) |

## Quick smoke test

```bash
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Najemcą jest Jan Kowalski z Krakowa, PESEL 90010112345. Przepisz to zdanie dokładnie."}]}' | jq
```

Expect HTTP 200 with the originals restored in the answer, while the request the
gateway sent to Ollama contained only synthetic values (verify the inbound side
with `POST /v1/pseudonymize`). macOS Docker is CPU-only (no Metal) → slow; for a
fast demo run Ollama natively on the host instead.
