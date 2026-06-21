# Quickstart / Validation: EPIC 6 — API Gateway Finalization

**Feature**: `specs/007-api-gateway-finalization` | Run from `apps/gateway-api` unless noted.

A validation/run guide. Implementation details live in `tasks.md` (next phase) and the code. See
`contracts/` for endpoint shapes and `data-model.md` for the models. **No new dependency** and **no
config change** — the chat *flow* is reused; only the response shape, three new endpoints, and one
logging middleware are added (plus the two agreed extensions: the port finish-reason and the pipeline
metrics).

## Prerequisites

- Redis 7 running (Compose network `pw-masters-secure-gateway`) with `REDIS_URL`, `REDIS_PASSWORD`,
  `REDIS_ENCRYPTION_KEY` set (EPIC 1); spaCy `pl_core_news_lg` available (EPIC 2).
- The **automated tests need no keys and no network** — provider clients are replaced by the reused
  `EchoProvider` / recording doubles (now returning `CompletionResult`) and Redis by `fakeredis`.
- For a **live** round-trip only: the keyless offline path needs a local Ollama at `OLLAMA_BASE_URL`
  with `qwen2.5:3b` pulled (see `.claude/rules/local-llm-ollama.md`); hosted providers need a real
  `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`.
- After backend **code** changes in Docker, **rebuild** the image (baked, not bind-mounted), passing the
  proxy CA: `CA_CERT_FILE=~/.certs/netskope-ca.pem docker compose build gateway-api`.

## 1. Offline validation — automated tests (no network, no keys)

```bash
uv run pytest                              # whole suite (EPIC 1–6) stays green
uv run pytest tests/test_chat_api.py tests/test_sessions_api.py \
              tests/test_providers_api.py tests/test_request_logging.py \
              tests/test_pipeline_inbound.py tests/llm_providers -q
```

Expected — these prove the epic without any live provider:

- **Chat contract** (`test_chat_api.py`): response carries `id`(`chatcmpl-…`), `object`,`created`,
  resolved `model`, `choices[0].finish_reason` normalized (recording double `length`→`"length"`; echo
  →`"stop"`), `anonymization_meta.entities_detected` per-type **over a multi-message history** with a
  matching `total_entities`, `timing_ms` with all six stages, and `input_anonymization` whose
  `replacements` offsets index the **original** latest user message. The **validation matrix** (empty
  messages; last role ≠ user; role `tool`; non-string content; model `mistral-large`) each returns
  **400 + preserved `session_id`** with no provider contacted. EPIC 4 no-PII assertions still hold;
  `message_count` increments only on success.
- **Sessions** (`test_sessions_api.py`): a turn detecting 2×PERSON + 1×PESEL → `GET` shows
  `entity_count==3`, `entities_by_type=={"PERSON":2,"PESEL":1}`, `message_count==1`,
  `ttl_remaining_seconds>0`; `DELETE` succeeds, then `GET`/`DELETE` → 404; unknown id → 404; a PII-free
  session → 404 on both verbs.
- **Providers** (`test_providers_api.py`): three entries with correct `requires_key`/`key_configured`;
  no key value in the body; answers while Redis is down (gate-exempt).
- **Logging** (`test_request_logging.py`): exactly **one** JSON line per request with the six timing
  stages; audit confirms **no** original / content / fake in the line; `endpoint` is the route
  template; a forced emit failure leaves the chat response 200 (error to stderr).
- **Pipeline inbound** (`test_pipeline_inbound.py`): `run_inbound` returns `entities_detected` over the
  whole history, last-message `replacements` with original offsets, and non-negative inbound timing.
- **Adapters** (`tests/llm_providers/`): each returns `CompletionResult` with the right `provider` name
  and normalized `finish_reason` (Anthropic `max_tokens`→`length`/`end_turn`→`stop`; Ollama
  `done_reason` normalized and **missing**→`stop`); the router passes `CompletionResult` through.

## 2. Live smoke — full chat response (keyless, offline Ollama)

```bash
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Najemcą jest Jan Kowalski z Krakowa, PESEL 90010112345. Przepisz to zdanie dokładnie."}]}' | jq
```

Expect HTTP 200 with the **full** body: `id`/`object`/`created`/`model`, `choices[0].finish_reason`
(`"stop"` or `"length"`), `anonymization_meta` (per-type counts, provider `ollama`, `timing_ms`), and
`input_anonymization` (synthetic latest message + replacements with original offsets). The request the
gateway sent to Ollama contained **only synthetic values** (cross-check with `POST /v1/pseudonymize`).

## 3. Live smoke — sessions & providers

```bash
# capture the session_id from the chat response above, then:
curl -s localhost:8000/v1/sessions/$SID | jq      # created_at, last_activity, ttl_remaining_seconds,
                                                  # entity_count, entities_by_type, message_count
curl -s -X DELETE localhost:8000/v1/sessions/$SID -o /dev/null -w '%{http_code}\n'  # 200
curl -s localhost:8000/v1/sessions/$SID -o /dev/null -w '%{http_code}\n'            # 404 (after delete)

curl -s localhost:8000/v1/providers | jq          # [{name,requires_key,key_configured} × 3]; no keys
```

## 4. Verify the log line (Constitution VIII)

With the stack running, send the chat request in §2 and inspect the gateway stdout:

```bash
docker compose logs --since=1m gateway-api | grep -E '"endpoint":"/v1/chat/completions"' | tail -1 | jq
```

Expect **one** JSON line for that request with `timestamp`, `session_id`, `endpoint`, `provider`,
`model`, `entities_detected` (counts only), and `timing_ms` (six stages). Confirm by eye that **no**
original name/PESEL, **no** message content, and **no** fake value appears anywhere in the line.

## Out of scope (do not test here)

Streaming/SSE; auth on any endpoint; token `usage`; per-request API-key headers; any new
anonymization/detection/generation/routing logic (EPICs 2–5, reused).
