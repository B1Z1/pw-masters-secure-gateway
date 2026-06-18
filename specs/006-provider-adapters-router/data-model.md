# Data Model: EPIC 5 — Provider Adapters & Model-Based Router

**Feature**: `specs/006-provider-adapters-router` | **Date**: 2026-06-17

EPIC 5 introduces **no new persisted data** — the Redis field layout and the AES-256-GCM envelope are
frozen (regression contract). It adds **no new transport models** either: the chat request/response
shapes (`ChatCompletionRequest`, `ChatCompletionResponse`, `Choice`, `ChatErrorBody`) and the
`ChatMessage` unit are reused unchanged from EPIC 4. The entities below are the **component contracts**
(adapters + router), the **additive** change to the error enum, and the **configuration delta**. Reused
EPIC 2/3/4 types (`AnonymizationPipeline`, `MappingStore`, `DetectedEntity`, the Redis schema,
`OllamaProvider`, `EchoProvider`) are unchanged and only referenced.

---

## 1. Provider port (reused; only the error enum is extended)

### LLMProvider (abstract — `base.py`) — UNCHANGED

| Member | Signature | Notes |
|--------|-----------|-------|
| `complete` | `async (messages: list[ChatMessage], *, model: str) -> str` | Returns assistant text; raises `LLMProviderError` on failure. Reused verbatim. |
| `health_check` | `async () -> bool` | Lightweight reachability probe; still **not consumed** by the chat path this epic (reserved for the future `/health`). |

### ChatMessage (`base.py`) — UNCHANGED

`{role: str, content: str}` — the OpenAI-compatible unit the pipeline pseudonymises and every adapter
consumes.

### LLMProviderError (`base.py`) — message/shape unchanged; `kind` enum **extended**

`Exception` with a readable message and `kind: ProviderErrorKind`.

```text
ProviderErrorKind = Literal[
    "unreachable",     # EPIC 4 — 503
    "missing_model",   # EPIC 4 — 503
    "timeout",         # EPIC 4 — 504
    "rate_limit",      # NEW    — 429 (no retry)
    "auth",            # NEW    — 503 (message names the missing/invalid key)
    "unknown_model",   # NEW    — 400 (raised by the router; lists recognized prefixes)
]
```

The three additions are **additive**; existing adapters and the EPIC 4 handler keep compiling. The
`kind → HTTP` map lives only in `api/chat.py` (see §5 and the [error-taxonomy contract](./contracts/error-taxonomy.md)).

---

## 2. OpenAIProvider (new — `openai_provider.py`)

Concrete adapter for `gpt-` models over `openai.AsyncOpenAI`.

**Construction**: `OpenAIProvider(api_key: str | None)`. The SDK client is built **lazily** on first
`complete()` with `max_retries=0`, and cached on the instance (D1/D8).

| Member | Behaviour |
|--------|-----------|
| `complete(messages, *, model)` | If `api_key` is missing → raise `LLMProviderError(kind="auth", "OPENAI_API_KEY is not configured")`. Else `await client.chat.completions.create(model=model, messages=[{role, content}, …])` — **no conversion**; a `system` message stays the first message. Return `choices[0].message.content`. If `choices[0].finish_reason == "length"` → log a **warning** (finish reason + model only) and still return the partial content (FR-005). Map SDK exceptions per §5. |
| `health_check()` | `True` when an API key is configured (lightweight; reserved for `/health`). |

**No conversion** (FR-004): the OpenAI shape is native. **No retry** (FR-020): client `max_retries=0`.
**Provider speaks for itself** (FR-006): `NotFoundError` (deprecated/unknown model) → `missing_model`
carrying the SDK message.

---

## 3. AnthropicProvider (new — `anthropic_provider.py`)

Concrete adapter for `claude-` models over `anthropic.AsyncAnthropic`.

**Construction**: `AnthropicProvider(api_key: str | None, max_tokens: int)`. SDK client built lazily on
first `complete()` with `max_retries=0`, cached on the instance.

| Member | Behaviour |
|--------|-----------|
| `complete(messages, *, model)` | If `api_key` missing → `LLMProviderError(kind="auth", "ANTHROPIC_API_KEY is not configured")`. Else normalize (below) → `await client.messages.create(model=model, max_tokens=self._max_tokens, messages=…[, system=…])`. Return the joined text blocks. Map SDK exceptions per §5. |
| `health_check()` | `True` when an API key is configured. |

### Message normalization (`list[ChatMessage]` → `(system, messages)`) — FR-007..FR-010

| Step | Rule |
|------|------|
| **system** | Concatenate the `content` of all `role == "system"` messages with `"\n\n"`; pass as the top-level `system` param. **Omit** the param entirely when there is no system content. |
| **messages** | Drop system messages; **merge** consecutive same-role turns (join `content` with `"\n\n"`) so the history alternates and begins with a user turn. |
| **max_tokens** | Always pass `self._max_tokens` (= `settings.anthropic_max_tokens`) — required by the API. |
| **other params** | `temperature`/`top_p`/… left at SDK defaults (out of scope). |

Return value: `"".join(block.text for block in response.content if block.type == "text")`.

**Documented limitation (Constitution IX)**: a history whose first non-system turn is an assistant turn
(atypical here) is not synthesised/dropped; Anthropic surfaces its own error if it ever occurs (D5).

---

## 4. LLMRouter (new — `llm_router.py`)

The composite `LLMProvider` that the chat endpoint calls (via `get_llm_provider`). Pure **prefix
dispatch**; lazily builds + caches each adapter (D2/D8).

**Construction**: `LLMRouter(provider_factories: Mapping[str, Callable[[], LLMProvider]], *, default_model: str)`
where keys are the recognized prefixes `"gpt-"`, `"claude-"`, `"ollama/"`. (`get_llm_provider` supplies
factories that read settings — see §6.)

| Member | Behaviour |
|--------|-----------|
| `complete(messages, *, model)` | Find the prefix that `model` starts with; lazily get-or-build that adapter (cached); for `"ollama/"` strip the prefix before delegating (`model[len("ollama/"):]`); delegate `await adapter.complete(messages, model=resolved)`. No prefix matches → raise `LLMProviderError(kind="unknown_model", "Unknown model '<model>'. Recognized prefixes: gpt-, claude-, ollama/")` **before** any adapter call (FR-015 / D7). |
| `health_check()` | Resolve the provider for `default_model`'s prefix and delegate its `health_check` (reserved for `/health`). |

**Invariant**: the router receives an already-pseudonymised array (the pipeline ran in the endpoint);
it never inspects message content, only the `model` string (Constitution I/IV).

---

## 5. Error taxonomy → HTTP (centralized in `api/chat.py`)

A single module-level map replaces EPIC 4's inline ternary:

```text
_ERROR_STATUS: dict[ProviderErrorKind, int] = {
    "unreachable":   503,
    "missing_model": 503,
    "timeout":       504,
    "rate_limit":    429,
    "auth":          503,
    "unknown_model": 400,
}
# in the handler: status = _ERROR_STATUS.get(exc.kind, 503)  (every body preserves session_id)
```

SDK exception → `kind` (applied inside each hosted adapter):

| SDK exception (OpenAI & Anthropic) | `kind` | HTTP |
|------------------------------------|--------|------|
| `APIConnectionError` | `unreachable` | 503 |
| `APITimeoutError` | `timeout` | 504 |
| `RateLimitError` (429) | `rate_limit` | 429 (no retry) |
| `AuthenticationError` / `PermissionDeniedError`, or missing key (pre-call) | `auth` | 503 (names the key) |
| `NotFoundError` (model) | `missing_model` | 503 |

`unknown_model` is raised by the router (§4), not an SDK; it maps to 400. See the
[error-taxonomy contract](./contracts/error-taxonomy.md).

---

## 6. Configuration delta (`config.py`)

| Setting | Env var | Default | Status |
|---------|---------|---------|--------|
| `default_llm_provider` | `DEFAULT_LLM_PROVIDER` | — | **REMOVED** (selection is by model prefix) |
| `default_model` | `DEFAULT_MODEL` | `ollama/qwen2.5:3b` | **CHANGED** from `gpt-4o` (keyless offline default) |
| `anthropic_max_tokens` | `ANTHROPIC_MAX_TOKENS` | `4096` | **NEW** (required on every Anthropic call) |
| `openai_api_key` | `OPENAI_API_KEY` | `None` | exists; optional at startup, auth-on-first-use |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `None` | exists; optional at startup, auth-on-first-use |
| `ollama_base_url` | `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | exists, unchanged |
| `ollama_timeout` | `OLLAMA_TIMEOUT` | `60.0` | exists, unchanged (long timeout for slow local models) |

`get_llm_provider()` (`@lru_cache`) builds the `LLMRouter` with factories:
`"gpt-" → OpenAIProvider(settings.openai_api_key)`,
`"claude-" → AnthropicProvider(settings.anthropic_api_key, settings.anthropic_max_tokens)`,
`"ollama/" → OllamaProvider(settings.ollama_base_url, settings.ollama_timeout)`, and
`default_model=settings.default_model`. **`main.py`** startup log drops the `provider=` field (the
removed setting); it still logs `model`, `redis_configured`, `session_ttl` — secrets never logged.

---

## 7. Reused / frozen (referenced, not modified)

- **Provider port internals** other than the `ProviderErrorKind` additions — `LLMProvider`,
  `ChatMessage`, `LLMProviderError` shape (FR-001).
- **`OllamaProvider`** (`ollama_provider.py`) — unchanged; now reached only via the router's `ollama/`
  branch with the prefix stripped (FR-011/FR-012).
- **`EchoProvider`** (`echo_provider.py`) — unchanged; pipeline/chat test double.
- **`AnonymizationPipeline`** (`pipeline/anonymization_pipeline.py`) and the inbound/outbound flow —
  unchanged (FR-024/FR-025/FR-026).
- **Chat transport models** — `ChatCompletionRequest {messages, session_id?, model?}`,
  `ChatCompletionResponse {session_id, choices}`, `Choice {index, message, finish_reason}`,
  `ChatErrorBody {detail, session_id}` — unchanged from EPIC 4 (full response contract still deferred).
- **`MappingStore`**, the Redis `fwd:/rev:/forms:/meta` schema, the AES-256-GCM envelope, the session
  TTL — frozen (Constitution III; regression contract).
