# Contract: `POST /v1/chat/completions` (full response + validation/error)

**Feature**: EPIC 6 | `gateway_api/api/chat.py` (response/validation) + `gateway_api/llm_providers/base.py`
(`CompletionResult`, finish-reason normalization). Flow is reused unchanged (D5/D6); the **response
shape** and **validation** are hardened. Models in [data-model.md](../data-model.md) §1–§2.

## Flow (unchanged)

`validate (400, before any provider call) → run_inbound (pseudonymize whole history) →
provider.complete (router → one adapter) → depseudonymize_text → build full response`. The provider
receives **only synthetic data** (Constitution I).

## Success response (HTTP 200)

```jsonc
{
  "id": "chatcmpl-7f3a…",            // "chatcmpl-" + uuid4().hex
  "object": "chat.completion",
  "created": 1750000000,             // unix seconds
  "model": "ollama/qwen2.5:3b",      // resolved model, UN-stripped (request.model or default)
  "choices": [
    { "index": 0,
      "message": { "role": "assistant", "content": "…originals restored for display…" },
      "finish_reason": "stop"        // real, normalized to "stop" | "length" (echo/stub → "stop")
    }
  ],
  "session_id": "…",                 // supplied or newly generated
  "anonymization_meta": {
    "entities_detected": { "PERSON": 2, "PESEL": 1 },   // per-type, over the WHOLE pseudonymized history
    "total_entities": 3,
    "provider": "ollama",            // concrete provider that served the request (self-reported)
    "model": "ollama/qwen2.5:3b",
    "processing_time_ms": 1234.5,    // == timing_ms.total
    "timing_ms": {
      "ner_analysis": 12.0, "fake_generation": 8.0, "redis_write": 5.0,
      "llm_request": 1200.0, "deanonymization": 9.5, "total": 1234.5
    }
  },
  "input_anonymization": {
    "pseudonymized_content": "…synthetic latest user message…",
    "replacements": [                // offsets index the ORIGINAL latest user message
      { "entity_type": "PERSON", "original": "Jan Kowalski", "fake": "Piotr Nowak", "start": 8, "end": 20 }
    ]
  }
}
```

**Field rules**
- `finish_reason`: `CompletionResult.finish_reason` (normalized — D2). OpenAI `length`→`length`;
  Anthropic `max_tokens`→`length`, `end_turn`/`stop_sequence`→`stop`; Ollama `done_reason` normalized;
  echo/missing → `stop`.
- `entities_detected`: counted over **every** message pseudonymized this turn (per detected occurrence
  per message); `total_entities` = sum. `{}`/`0` when no PII.
- `input_anonymization`: the **latest user message only**. `replacements=[]` when it has no PII. Returning
  `original` here is allowed — the client↔gateway hop is trusted (FR-006).
- `model`: the resolved model as the caller sees it (un-stripped); the `ollama/` strip is internal to the
  router.
- `timing_ms` is the **same object** emitted to the log line (FR-005 / D11).

## Validation (HTTP 400, before any provider call — every body preserves `session_id`)

| Condition | Result |
|-----------|--------|
| `messages` empty | 400 `{"detail":"messages must not be empty","session_id":…}` |
| last message role ≠ `user` | 400 `{"detail":"the last message must be a user turn",…}` |
| any message role ∉ {system,user,assistant} | 400 (clear message) |
| any message `content` missing / not a string | 400 (clear message) |
| unknown model (no recognized prefix) | 400 listing `gpt-`, `claude-`, `ollama/` (from the router) |

A pre-handler 422 is **avoided** by the permissive request model (D6), so all four input cases surface as
400 *with* `session_id`.

## Provider-error mapping (reused — `_ERROR_STATUS`, D5 §5)

`unreachable`/`missing_model`/`auth` → **503** (auth names the missing key); `timeout` → **504**;
`rate_limit` → **429** (no retry); `unknown_model` → **400**. Every error body preserves `session_id`;
inbound mappings already written are **not** rolled back (FR-010).

## Side effects

- On **success only**, `message_count` is incremented for the session — and only if the session already
  has stored state (PII was detected at least once); PII-free sessions stay stateless (D7).
- Exactly one structured log line is emitted by the logging middleware (see
  [logging-middleware contract](./logging-middleware.md)).

## Acceptance assertions (map to spec)

- Full body shape + real normalized `finish_reason` (SC-002, SC-004; FR-002/FR-003).
- `entities_detected` over whole history + `input_anonymization` offsets into the original (SC-003;
  FR-005/FR-006).
- Validation matrix → 400 preserving `session_id`, no provider contacted (SC-008; FR-007/FR-008/FR-010).
- Provider only ever sees synthetic data; nothing leaks to logs (SC-009; FR-024).
