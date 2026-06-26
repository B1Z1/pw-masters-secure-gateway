# Contract: Additive `echo/` provider route (the only gateway-api change)

This is the **sole** change to `apps/gateway-api`. It is additive, Constitution-IV-sanctioned, and alters
no existing behaviour. It exists so Stage 2 can drive the **live** gateway with a deterministic provider
over HTTP (research D2; user-confirmed 2026-06-25).

## Change

In `apps/gateway-api/gateway_api/llm_providers/__init__.py`, add one factory entry to the router map in
`get_llm_provider()`:

```python
return LLMRouter(
    {
        "gpt-": lambda: OpenAIProvider(settings.openai_api_key),
        "claude-": lambda: AnthropicProvider(settings.anthropic_api_key, settings.anthropic_max_tokens),
        "ollama/": lambda: OllamaProvider(settings.ollama_base_url, settings.ollama_timeout),
        "echo/": lambda: EchoProvider(),   # NEW — deterministic, offline; enables eval Stage 2
    },
    default_model=settings.default_model,
)
```

`EchoProvider` already exists and is already imported in this module. No pipeline, validation, store, or
existing-prefix behaviour changes.

## Behaviour

- A chat request with `model: "echo/echo"` (any name after `echo/`) routes to `EchoProvider`, which returns
  the **last user message's content** with `finish_reason="stop"`, `provider="echo"`.
- In the chat flow that content is the **pseudonymized** last user turn, so the gateway de-pseudonymizes it
  back to the original on the way out — giving a clean, deterministic round-trip with `llm_request ≈ 0 ms`.
- `default_model` is unchanged (still `ollama/qwen2.5:3b`); the echo route is **opt-in per request**, never
  the default. Existing `gpt-`/`claude-`/`ollama/` routing and the unknown-prefix → 400 behaviour are
  unchanged.

## Test (gateway-api side)

`apps/gateway-api/tests/llm_providers/test_llm_router.py` — assert `model="echo/echo"` dispatches to the
`EchoProvider` and yields `CompletionResult(provider="echo", finish_reason="stop")`, and that the three
existing prefixes and the unknown-model 400 are unaffected.

## Non-goals

- No new docker service, no new dependency, no config flag. (Reachability is purely the per-request `model`
  value.)
- The harness does **not** require this route for **Stage 1** (Stage 1 is no-LLM).
