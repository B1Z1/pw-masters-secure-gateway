# Quickstart / Validation: EPIC 5 — Provider Adapters & Model-Based Router

**Feature**: `specs/006-provider-adapters-router` | Run from `apps/gateway-api` unless noted.

This is a validation/run guide. Implementation details live in `tasks.md` (next phase) and the code.
See `contracts/` for component shapes and `data-model.md` for the models. The provider **port** is reused
unchanged from EPIC 4 — only adapters, the router, the error map, and config change.

## Prerequisites

- Redis 7 running (Compose network `pw-masters-secure-gateway`) with `REDIS_URL`, `REDIS_PASSWORD`,
  `REDIS_ENCRYPTION_KEY` set (EPIC 1); spaCy `pl_core_news_lg` available (EPIC 2).
- **New dependencies** installed: `openai`, `anthropic`. Native: `uv sync`. Docker image: **rebuild**
  (deps install through the proxy — pass the build CA):
  `CA_CERT_FILE=~/.certs/netskope-ca.pem docker compose build gateway-api`.
- The **automated tests need no keys and no network** — the OpenAI/Anthropic SDK clients are mocked and
  the echo/stub provider is reused.
- For a **live** hosted round-trip only: a real `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`. For the
  **keyless offline** path: a local Ollama reachable at `OLLAMA_BASE_URL` with `qwen2.5:3b` pulled.

## 1. Offline validation — automated tests (no network, no keys)

```bash
uv run pytest                                   # whole suite (EPIC 1–5) stays green
uv run pytest tests/llm_providers -q tests/test_chat_api.py
```

Expected — these prove the epic without any live provider:

- **Router** (`tests/llm_providers/test_llm_router.py`): `gpt-4o` → OpenAI adapter; `claude-3-5-sonnet`
  → Anthropic adapter; `ollama/qwen2.5:3b` → Ollama adapter receiving **`qwen2.5:3b`** (prefix
  stripped); an unrecognised model raises `unknown_model`; a provider with a missing key raises `auth`;
  `health_check` delegates to the default model's provider (SC-001, SC-002, SC-003).
- **OpenAI adapter** (`test_openai_provider.py`): native pass-through (system stays first);
  `finish_reason == "length"` logs a warning **and** returns the partial content; SDK exceptions map to
  `rate_limit`/`auth`/`missing_model`/`timeout`/`unreachable`; `create` called **once** (no retry)
  (SC-005).
- **Anthropic adapter** (`test_anthropic_provider.py`): system messages lifted + concatenated into the
  `system` param; no-system case omits it; consecutive same-role merged (user-first alternation);
  `max_tokens` passed; exceptions map; no retry (SC-004).
- **Endpoint** (`tests/test_chat_api.py`): `rate_limit` → **429**, `auth` → **503** (detail names the
  key), unknown model → **400**, each **preserving `session_id`**; the EPIC 4 **no-PII** assertions (no
  original in the captured provider payload or in `caplog`) still hold on the routed path (SC-006,
  SC-008).
- **Regression**: EPIC 2/3/4 suites unchanged and green — public behaviour, Redis layout, AES-256-GCM
  envelope frozen; the Ollama adapter tests are untouched.

## 2. Live validation — routing across real providers (manual, optional)

With Redis up and the app running (`uv run uvicorn gateway_api.main:app --reload`, or
`docker compose up`):

### a) Keyless offline default → Ollama

```bash
# No model field → settings.default_model = "ollama/qwen2.5:3b" → routed to Ollama.
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "messages": [{"role":"user","content":"Streść umowę: najemca Jan Kowalski (PESEL 90010112345) z Krakowa."}]
}' | jq
```

Expect **200** with originals restored; the request Ollama received used `qwen2.5:3b` and contained only
synthetic values. (See [`dev/ollama/README.md`](../../dev/ollama/README.md) / the
`local-llm-ollama` rule — now using **prefixed** model names.)

### b) Hosted providers (need keys)

```bash
# Routes to OpenAI:
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model":"gpt-4o", "messages":[{"role":"user","content":"…"}]}' | jq
# Routes to Anthropic:
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model":"claude-3-5-sonnet-20241022", "messages":[{"role":"user","content":"…"}]}' | jq
```

Expect **200** with originals restored; each provider saw only synthetic values; gateway logs carry
`session_id`, model, counts, status — no PII (Constitution VIII).

### c) Error paths

```bash
# Unknown model → 400 listing prefixes, nothing sent to any provider:
curl -si localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model":"mistral-large", "messages":[{"role":"user","content":"hi"}]}'

# Hosted provider with its key unset → 503 naming the key:
#   (unset OPENAI_API_KEY, then send a gpt- request)
```

Spot-check: a provider rate limit → **429** (no retry); a missing key → **503** naming
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`; each error echoes `session_id`.

## 3. Done criteria

- [ ] `uv run pytest` green (all epics) — new deps installed; image rebuilt if running in Docker.
- [ ] Router dispatches `gpt-`/`claude-`/`ollama/` correctly; `ollama/` prefix stripped before send.
- [ ] Unknown model → 400 (prefixes listed, nothing sent); no model → Ollama default works keyless.
- [ ] Anthropic conversion (system lifted/concatenated, alternation, `max_tokens`) verified.
- [ ] OpenAI native pass-through; length truncation → warning + partial content.
- [ ] `rate_limit` → 429 (no retry), `auth` → 503 naming the key; startup with no keys succeeds.
- [ ] No PII in any provider payload or in logs, for every provider; EPIC 2/3/4 regression green.
- [ ] Postman "Chat" folder + `dev/ollama` docs use prefixed model names.
