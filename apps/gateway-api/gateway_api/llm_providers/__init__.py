"""LLM provider port + the providers wired this epic (Epic 4).

``get_llm_provider`` is the FastAPI dependency the chat endpoint resolves. This
epic talks to Ollama directly; ``DEFAULT_LLM_PROVIDER`` is intentionally NOT
consulted here — the model-based provider router (which would honour it) is a
later epic. Tests override this dependency with a stub/echo provider.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import ChatMessage, LLMProvider, LLMProviderError
from .echo_provider import EchoProvider
from .ollama_provider import OllamaProvider

__all__ = [
    "ChatMessage",
    "EchoProvider",
    "LLMProvider",
    "LLMProviderError",
    "OllamaProvider",
    "get_llm_provider",
]


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()

    return OllamaProvider(
        base_url=settings.ollama_base_url, timeout=settings.ollama_timeout
    )
