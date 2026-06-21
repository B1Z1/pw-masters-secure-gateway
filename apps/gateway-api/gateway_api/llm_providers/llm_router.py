"""Model-based provider router (Epic 5, FR-013..FR-018).

``LLMRouter`` is itself an ``LLMProvider`` (a composite): the chat endpoint keeps
calling one provider, and the router dispatches per request by the model's prefix
— ``gpt-`` → OpenAI, ``claude-`` → Anthropic, ``ollama/`` → Ollama (with the
``ollama/`` prefix stripped before the name is sent on, so ``ollama/qwen2.5:3b``
reaches Ollama as ``qwen2.5:3b``). An unrecognized prefix is a client error raised
as ``LLMProviderError(kind="unknown_model")`` (→ 400) BEFORE any adapter is called
— Ollama is deliberately not a catch-all. Adapters are built lazily from per-prefix
factories and cached, so a provider whose key is missing only errors on first use,
not at startup (FR-022, Constitution IV).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .base import ChatMessage, CompletionResult, LLMProvider, LLMProviderError

_OLLAMA_PREFIX = "ollama/"


class LLMRouter(LLMProvider):
    def __init__(
        self,
        provider_factories: Mapping[str, Callable[[], LLMProvider]],
        *,
        default_model: str,
    ) -> None:
        # Insertion order defines the recognized-prefix list shown in the
        # unknown-model error (and the match order).
        self._factories = dict(provider_factories)
        self._default_model = default_model
        self._adapters: dict[str, LLMProvider] = {}

    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        prefix, model_to_send = self._resolve(model)
        return await self._adapter_for(prefix).complete(messages, model=model_to_send)

    async def health_check(self) -> bool:
        prefix, _ = self._resolve(self._default_model)
        return await self._adapter_for(prefix).health_check()

    def _resolve(self, model: str) -> tuple[str, str]:
        """Return ``(prefix, model-to-send)``; raise ``unknown_model`` if none match.

        The ``ollama/`` prefix is stripped from the outgoing model name (FR-014);
        other prefixes leave the model unchanged.
        """
        for prefix in self._factories:
            if model.startswith(prefix):
                if prefix == _OLLAMA_PREFIX:
                    return prefix, model[len(_OLLAMA_PREFIX) :]
                return prefix, model
        recognized_prefixes = ", ".join(self._factories)
        raise LLMProviderError(
            f"Unknown model '{model}'. Recognized prefixes: {recognized_prefixes}",
            kind="unknown_model",
        )

    def _adapter_for(self, prefix: str) -> LLMProvider:
        """Lazily build and cache the adapter for a prefix (FR-022, D8)."""
        if prefix not in self._adapters:
            self._adapters[prefix] = self._factories[prefix]()
        return self._adapters[prefix]
