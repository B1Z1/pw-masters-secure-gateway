# Contract: `OpenAIProvider`

**Feature**: EPIC 5 | `gateway_api/llm_providers/openai_provider.py` | Implements the EPIC 4
`LLMProvider` port for models with prefix `gpt-`. Uses the official `openai.AsyncOpenAI` client.

## Construction

`OpenAIProvider(api_key: str | None)`. The SDK client is built **lazily** on first `complete()` with
**`max_retries=0`** (no auto-retry — FR-020) and cached on the instance (keys optional at startup — D8).

## `complete(messages, *, model) -> str`

1. If `api_key` is missing/blank → raise `LLMProviderError(kind="auth", "OPENAI_API_KEY is not configured")`
   (no client built).
2. `await client.chat.completions.create(model=model, messages=[{role, content} for m in messages])` —
   **no conversion** (OpenAI is the native shape); a `system` message is passed through as the **first**
   message (FR-004).
3. Read `choices[0]`. If `finish_reason == "length"` → **log a warning** (finish reason + model only,
   never content) and **still return** `choices[0].message.content` (the partial answer — FR-005).
4. Otherwise return `choices[0].message.content`.

## `health_check() -> bool`

Returns whether an API key is configured (lightweight; reserved for `/health`).

## Exception → `LLMProviderError.kind` (no retry; SDK message preserved)

| OpenAI SDK exception | `kind` | HTTP (via chat.py) |
|----------------------|--------|--------------------|
| `APIConnectionError` | `unreachable` | 503 |
| `APITimeoutError` | `timeout` | 504 |
| `RateLimitError` (429) | `rate_limit` | 429 |
| `AuthenticationError` / `PermissionDeniedError` | `auth` (names the key) | 503 |
| `NotFoundError` (deprecated/unknown model) | `missing_model` (carries the SDK message — FR-006) | 503 |

## Acceptance assertions (map to spec)

- System message sent first, no conversion (SC-001, FR-004).
- `finish_reason == "length"` → warning logged + partial content returned (SC-005, FR-005).
- Deprecated/unknown model → provider's own error surfaced (SC-005, FR-006).
- `create` called exactly once per `complete` (no retry — FR-020).
- No original PII in logs or in the outgoing payload (SC-008, Constitution VIII).
