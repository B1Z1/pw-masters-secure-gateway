# Contract: `POST /v1/chat/completions`

**Feature**: EPIC 4 | OpenAI-compatible **in shape**, minimal **in content** (full response contract
is a later epic). Gated by the EPIC 1 `redis_availability_gate` (requires Redis → **not** gate-exempt).

## Request

```json
{
  "messages": [
    {"role": "user", "content": "Umowę zawarł Jan Kowalski, PESEL 90010112345, z Krakowa."}
  ],
  "session_id": "optional-hex",
  "model": "optional-ollama-model"
}
```

- `messages`: non-empty array of `{role, content}`. **Last** message MUST be `role == "user"`.
- `session_id`: optional; absent/blank → generated and returned.
- `model`: optional; defaults to `settings.default_model`.

## Flow (happy path)

1. Validate request (else **400**, no LLM call).
2. `session_id := request.session_id or uuid4().hex`.
3. `fake_messages = pipeline.pseudonymize_messages(session_id, messages)` — every message
   pseudonymised (FR-005); only synthetic values leave the gateway.
4. `fake_answer = provider.complete(fake_messages, model=model)`.
5. `answer = pipeline.depseudonymize_text(session_id, fake_answer)` — exact + inflection + fuzzy.
6. Return 200.

## Response 200

```json
{
  "session_id": "…",
  "choices": [
    {"index": 0, "message": {"role": "assistant", "content": "…originals restored…"}, "finish_reason": null}
  ]
}
```

## Errors (each preserves `session_id`)

| Status | When | Body |
|--------|------|------|
| **400** | empty `messages`, or last message not `role=="user"` | `{detail, session_id?}` |
| **503** | Redis down (gate), or provider `kind ∈ {unreachable, missing_model}` | `{detail, session_id}` |
| **504** | provider `kind == "timeout"` (exceeds `OLLAMA_TIMEOUT`) | `{detail, session_id}` |

## Acceptance assertions (map to spec)

- Outgoing provider payload contains **no original PII**; restored answer contains originals (SC-001).
- Multi-turn: re-sent earlier assistant PII is re-pseudonymised, same original → same fake (SC-002).
- No original PII in logs (SC-007, Constitution VIII).
- Streaming/SSE: **not** offered (Constitution V).
