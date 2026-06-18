"""LLM provider port + the providers wired this epic (Epic 4/5).

``get_llm_provider`` is the FastAPI dependency the chat endpoint resolves. Epic 5
returns the model-based ``LLMRouter`` (a composite ``LLMProvider``) that dispatches
per request by the model prefix, replacing Epic 4's hardcoded ``OllamaProvider``.
The chat endpoint and pipeline are unchanged and never see a concrete provider
(Constitution IV). Provider API keys stay optional at startup — an adapter is built
lazily and only errors (auth → 503) on first use of a provider that needs a key.
Tests override this dependency with a stub/echo provider (or a router built from
doubles), bypassing the real wiring.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .anthropic_provider import AnthropicProvider
from .base import ChatMessage, LLMProvider, LLMProviderError
from .echo_provider import EchoProvider
from .llm_router import LLMRouter
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

__all__ = [
    "AnthropicProvider",
    "ChatMessage",
    "EchoProvider",
    "LLMProvider",
    "LLMProviderError",
    "LLMRouter",
    "OllamaProvider",
    "OpenAIProvider",
    "get_llm_provider",
]


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()

    return LLMRouter(
        {
            "gpt-": lambda: OpenAIProvider(settings.openai_api_key),
            "claude-": lambda: AnthropicProvider(
                settings.anthropic_api_key, settings.anthropic_max_tokens
            ),
            "ollama/": lambda: OllamaProvider(
                settings.ollama_base_url, settings.ollama_timeout
            ),
        },
        default_model=settings.default_model,
    )
