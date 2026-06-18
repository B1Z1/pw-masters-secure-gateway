"""LLMRouter — prefix dispatch, ollama/ strip, lazy caching (US1/US2/US6).

Pure, network-free: the per-prefix adapters are recording doubles injected via the
factory map, so routing is asserted without any real provider.
"""

from __future__ import annotations

import pytest

from gateway_api.llm_providers.base import ChatMessage, LLMProvider, LLMProviderError
from gateway_api.llm_providers.llm_router import LLMRouter

_MESSAGES = [ChatMessage(role="user", content="cześć")]


class _RecordingProvider(LLMProvider):
    def __init__(self, name: str):
        self.name = name
        self.calls: list[str] = []  # model strings received

    async def complete(self, messages, *, model):
        self.calls.append(model)
        return f"{self.name}:{model}"

    async def health_check(self):
        return True


def _make_router(default_model: str = "ollama/qwen2.5:3b"):
    providers = {
        "gpt-": _RecordingProvider("openai"),
        "claude-": _RecordingProvider("anthropic"),
        "ollama/": _RecordingProvider("ollama"),
    }
    build_counts = {prefix: 0 for prefix in providers}

    def factory(prefix: str):
        def _build():
            build_counts[prefix] += 1
            return providers[prefix]

        return _build

    router = LLMRouter(
        {prefix: factory(prefix) for prefix in providers},
        default_model=default_model,
    )
    return router, providers, build_counts


async def test_gpt_routes_to_openai():
    router, providers, _ = _make_router()
    result = await router.complete(_MESSAGES, model="gpt-4o")
    assert result == "openai:gpt-4o"
    assert providers["gpt-"].calls == ["gpt-4o"]
    assert providers["claude-"].calls == []
    assert providers["ollama/"].calls == []


async def test_claude_routes_to_anthropic():
    router, providers, _ = _make_router()
    await router.complete(_MESSAGES, model="claude-3-5-sonnet")
    assert providers["claude-"].calls == ["claude-3-5-sonnet"]
    assert providers["gpt-"].calls == []
    assert providers["ollama/"].calls == []


async def test_ollama_routes_with_prefix_stripped():
    router, providers, _ = _make_router()
    await router.complete(_MESSAGES, model="ollama/qwen2.5:3b")
    # The "ollama/" prefix is stripped before the name reaches the adapter.
    assert providers["ollama/"].calls == ["qwen2.5:3b"]
    assert providers["gpt-"].calls == []
    assert providers["claude-"].calls == []


async def test_unknown_model_raises_and_dispatches_nothing():
    router, providers, _ = _make_router()
    with pytest.raises(LLMProviderError) as excinfo:
        await router.complete(_MESSAGES, model="mistral-large")
    assert excinfo.value.kind == "unknown_model"
    message = str(excinfo.value)
    assert "gpt-" in message
    assert "claude-" in message
    assert "ollama/" in message
    assert all(provider.calls == [] for provider in providers.values())


async def test_adapters_built_lazily_and_cached():
    router, _, build_counts = _make_router()
    await router.complete(_MESSAGES, model="gpt-4o")
    await router.complete(_MESSAGES, model="gpt-4o")
    assert build_counts["gpt-"] == 1  # built once, then cached
    assert build_counts["claude-"] == 0  # never built (unused)
    assert build_counts["ollama/"] == 0


async def test_health_check_delegates_to_default_model_provider():
    router, _, build_counts = _make_router(default_model="ollama/qwen2.5:3b")
    assert await router.health_check() is True
    assert build_counts["ollama/"] == 1
    assert build_counts["gpt-"] == 0
    assert build_counts["claude-"] == 0
