# Contract: `LLMRouter` (model-based provider router)

**Feature**: EPIC 5 | `gateway_api/llm_providers/llm_router.py` | Satisfies Constitution IV: the chat
endpoint keeps calling **one** provider; the router dispatches per request by **model prefix**. The
router **is** an `LLMProvider` (composite) and reuses the EPIC 4 port unchanged.

## Construction

```text
LLMRouter(
    provider_factories: Mapping[str, Callable[[], LLMProvider]],  # keys: "gpt-", "claude-", "ollama/"
    *, default_model: str,
)
```

- Each factory is invoked **lazily** on first use and the resulting adapter is **cached** (D8).
- `default_model` is used only by `health_check` (the endpoint resolves the per-request default — D2).

## `complete(messages, *, model) -> str`

Routing table (prefix only — no model-name allowlist):

| `model` starts with | Adapter | Model passed on |
|---------------------|---------|-----------------|
| `gpt-` | OpenAI | `model` unchanged |
| `claude-` | Anthropic | `model` unchanged |
| `ollama/` | Ollama | `model` with `ollama/` **stripped** (`ollama/qwen2.5:3b` → `qwen2.5:3b`) |
| (none of the above) | — | raise `LLMProviderError(kind="unknown_model", "Unknown model '<model>'. Recognized prefixes: gpt-, claude-, ollama/")` — **before any adapter call** |

- The `messages` array is already pseudonymised by the pipeline; the router never inspects `content`.
- On a matched prefix, the router delegates `await adapter.complete(messages, model=resolved)` and
  returns its result; adapter `LLMProviderError`s propagate unchanged.

## `health_check() -> bool`

Resolves the provider for `default_model`'s prefix and delegates its `health_check`. Reserved for the
future `/health` endpoint (not consumed by the chat path this epic).

## Wiring (`llm_providers/__init__.py`)

`get_llm_provider()` (kept `@lru_cache`) builds and returns the `LLMRouter` with factories reading
`Settings` (OpenAI/Anthropic from keys, Ollama from base-url/timeout) and `default_model` — **replacing**
the hardcoded `OllamaProvider`. Tests override the FastAPI dependency to bypass the router.

## Acceptance assertions (map to spec)

- `gpt-4o` → OpenAI; `claude-3-5-sonnet` → Anthropic; `ollama/qwen2.5:3b` → Ollama receives
  `qwen2.5:3b` (SC-001).
- Unrecognised model → `unknown_model` → endpoint **400** listing prefixes; nothing sent to any
  provider (SC-002, FR-015).
- No model in request → endpoint applies `settings.default_model` (`ollama/…`) → routed to Ollama;
  completes with no keys configured (SC-003).
- Pipeline/endpoint unchanged to support the three providers (SC-007, Constitution IV).

## Out of scope (later epics / non-goals)

Streaming; per-provider model-name allowlist; retries/backoff; the `/health` endpoint that would consume
`health_check`.
