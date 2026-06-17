# Quickstart / Validation: EPIC 4 — Anonymization Pipeline & First LLM Round-Trip

**Feature**: `specs/005-anonymization-pipeline` | Run from `apps/gateway-api` unless noted.

This is a validation/run guide. Implementation details live in `tasks.md` (next phase) and the code.
See `contracts/` for interface shapes and `data-model.md` for the component models.

## Prerequisites

- Redis 7 running (Docker Compose network `pw-masters-secure-gateway`) and `REDIS_URL`,
  `REDIS_PASSWORD`, `REDIS_ENCRYPTION_KEY` set (EPIC 1).
- spaCy `pl_core_news_lg` available (EPIC 2); detection model ready.
- For the **live** LLM round-trip only: a local Ollama server reachable at `OLLAMA_BASE_URL` with an
  installed model; set `DEFAULT_MODEL` to that model and `OLLAMA_TIMEOUT` as desired. The automated
  tests do **not** need Ollama (they use the echo/stub provider).

## 1. Offline validation — automated tests (no network, no Ollama)

```bash
uv run pytest                       # whole suite (EPIC 1–4) stays green
uv run pytest tests/test_chat_api.py tests/pseudonym_vault/test_fuzzy_restoration.py -q
```

Expected — these prove the epic without a live LLM:
- **Pipeline round-trip** (echo provider): a message with a person + city + PESEL is pseudonymised,
  echoed, and de-pseudonymised; the captured provider payload has **no original PII**; the originals
  are restored in the result (SC-001, SC-005).
- **Multi-turn**: a second turn re-sending an earlier (de-pseudonymised) assistant message
  re-pseudonymises every original, same original → same fake (SC-002).
- **Fuzzy fallback**: an inflected fake PERSON/LOCATION the form table missed is restored in base
  form; a perturbed PESEL/IBAN/EMAIL_ADDRESS/PHONE_NUMBER is **not** fuzzed; a look-alike non-PII token
  and an invented name pass through untouched; an ambiguous tie is skipped (SC-003, SC-004).
- **Errors**: empty `messages` and a non-user last message → 400; stub provider raising
  `kind="unreachable"`/`"missing_model"` → 503; `kind="timeout"` → 504; `session_id` preserved in each
  error body (SC-006).
- **Regression**: `tests/test_pseudonymize_api.py`, `tests/pseudonym_vault/test_mapping_store.py`
  unchanged and green — EPIC 3 behaviour, Redis layout, AES-256-GCM envelope frozen (SC-008).

## 2. Live validation — real Ollama round-trip (manual, optional)

```bash
# with Redis up, Ollama up, DEFAULT_MODEL set to an installed model:
uv run uvicorn gateway_api.main:app --reload    # or: nx serve gateway-api / docker compose up

curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "messages": [{"role":"user","content":"Streść umowę: najemca Jan Kowalski (PESEL 90010112345) z Krakowa."}]
}' | jq
```

Expected:
- Response `200` with `session_id` and `choices[0].message.content` containing the **original** name,
  city, and PESEL restored in place.
- The request actually sent to Ollama (inspect server logs / a packet capture) contained only
  **synthetic** values — never the originals (SC-001, SC-007).
- Gateway logs show `session_id`, entity types/counts, timings — **no** original PII (Constitution
  VIII).

Failure modes to spot-check:
- Stop Ollama → `503` with a readable detail and the `session_id` echoed.
- Set `OLLAMA_TIMEOUT` very low against a slow model → `504`, `session_id` echoed.
- `{"messages": []}` → `400`.

## 3. Done criteria

- [ ] `uv run pytest` green (all epics).
- [ ] Offline chat round-trip restores originals with no PII in the provider payload or logs.
- [ ] 400 / 503 / 504 behave per the table, each preserving `session_id`.
- [ ] EPIC 3 `/v1/pseudonymize` + `/v1/depseudonymize` round-trip unchanged.
- [ ] (If demoing live) a real Ollama answer about a Polish contract returns with originals restored.
