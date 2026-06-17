# Contract: LLM Provider Port

**Feature**: EPIC 4 | `gateway_api/llm_providers/` | Satisfies Constitution IV (Provider Agnosticism):
the pipeline/endpoint depend ONLY on this interface; adding a provider requires no pipeline change.

## `LLMProvider` (abstract, `base.py`)

```text
async complete(messages: list[ChatMessage], *, model: str) -> str
async health_check() -> bool
```

- `complete`: send the whole (already-pseudonymised) messages array; return assistant text. MUST raise
  `LLMProviderError` on any failure (never return partial/garbled text).
- `health_check`: cheap reachability probe; `True` if the provider is usable. No raise.

## `LLMProviderError` (`base.py`)

`Exception` with `kind: Literal["unreachable", "missing_model", "timeout"]` + readable message.
Handler mapping: `unreachable`/`missing_model` → **503**, `timeout` → **504**.

## `OllamaProvider` (`ollama_provider.py`) — the one real provider this epic

- `complete`: `POST {OLLAMA_BASE_URL}/api/chat` body `{model, messages, stream: false}`,
  `timeout=OLLAMA_TIMEOUT`; return `json()["message"]["content"]`.
- `health_check`: `GET {OLLAMA_BASE_URL}/api/tags` → 2xx.
- Mapping: `httpx.ConnectError|ConnectTimeout → unreachable`; 404 / "model not found" →
  `missing_model`; `httpx.ReadTimeout|TimeoutException → timeout`.
- `stream=False` enforces Constitution V (full answer before de-pseudonymisation).

## `EchoProvider` (`echo_provider.py`) — deterministic test double

- `complete`: returns a fixed, network-free transform of the conversation (e.g. echoes the last user
  message content) so round-trip tests assert restoration without a model.
- `health_check`: `True`.

## Out of scope (later epics)

OpenAI/Anthropic adapters; model-based provider router; rich response (usage, finish_reason
passthrough); streaming.
