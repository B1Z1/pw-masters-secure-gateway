# Contract: `AnthropicProvider`

**Feature**: EPIC 5 | `gateway_api/llm_providers/anthropic_provider.py` | Implements the EPIC 4
`LLMProvider` port for models with prefix `claude-`. Uses the official `anthropic.AsyncAnthropic` client.
Anthropic's message rules differ from OpenAI's, so the adapter **converts** the messages.

## Construction

`AnthropicProvider(api_key: str | None, max_tokens: int)`. The SDK client is built **lazily** on first
`complete()` with **`max_retries=0`** and cached on the instance. `max_tokens` comes from
`settings.anthropic_max_tokens` (FR-010).

## Message normalization (`list[ChatMessage]` → `(system, messages)`)

| Concern | Rule (FR-007..FR-010) |
|---------|------------------------|
| **system** | Concatenate the `content` of every `role == "system"` message (in order) with `"\n\n"`; pass as the top-level `system` parameter. If there is **no** system content, **omit** the parameter entirely. System is **never** a message role. |
| **messages** | Drop system messages; from the remaining user/assistant turns **merge any two consecutive same-role messages** into one (join `content` with `"\n\n"`) so the history **alternates** and **begins with a user turn**. |
| **max_tokens** | Always pass `self._max_tokens` — **required** by the Messages API. |
| **other** | `temperature`/`top_p`/etc. left at SDK defaults (out of scope). |

## `complete(messages, *, model) -> str`

1. If `api_key` missing/blank → `LLMProviderError(kind="auth", "ANTHROPIC_API_KEY is not configured")`.
2. Normalize as above → `await client.messages.create(model=model, max_tokens=self._max_tokens, messages=…[, system=…])`.
3. Return `"".join(block.text for block in response.content if block.type == "text")`.

## `health_check() -> bool`

Returns whether an API key is configured (reserved for `/health`).

## Exception → `LLMProviderError.kind`

`APIConnectionError → unreachable` (503), `APITimeoutError → timeout` (504),
`RateLimitError → rate_limit` (429, no retry), `AuthenticationError`/`PermissionDeniedError → auth`
(503, names the key), `NotFoundError → missing_model` (503).

## Acceptance assertions (map to spec)

- System message(s) lifted + concatenated into the top-level `system` param; no system → param omitted
  (SC-004, FR-008).
- Two consecutive user messages merged → history starts with user and alternates (SC-004, FR-009).
- `max_tokens` present on every call (SC-004, FR-010).
- Exceptions map to the right kinds; `create` called once (no retry — FR-020).
- No original PII in logs or in the outgoing payload (SC-008, Constitution VIII).

## Documented limitation (Constitution IX)

A history whose first non-system turn is an *assistant* turn is atypical for this gateway and is not
synthesised/dropped; Anthropic surfaces its own error if it ever occurs.
