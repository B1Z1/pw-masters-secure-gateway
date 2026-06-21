"""AnthropicProvider — message normalization, max_tokens, error→kind, no retry (US3).

The async Anthropic client is mocked (no network, no key needed beyond a dummy).
"""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from gateway_api.llm_providers.anthropic_provider import AnthropicProvider
from gateway_api.llm_providers.base import ChatMessage, LLMProviderError


def _response(*text_blocks, stop_reason="end_turn"):
    content = [SimpleNamespace(type="text", text=t) for t in text_blocks]
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class _FakeMessages:
    def __init__(self, *, result=None, exc=None):
        self._result = result if result is not None else _response("ok")
        self._exc = exc
        self.calls = 0
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self._exc is not None:
            raise self._exc
        return self._result


class _FakeClient:
    def __init__(self, messages):
        self.messages = messages


def _patch(monkeypatch, messages):
    captured: dict = {}

    def _factory(**kwargs):
        captured["client_kwargs"] = kwargs
        return _FakeClient(messages)

    monkeypatch.setattr(
        "gateway_api.llm_providers.anthropic_provider.anthropic.AsyncAnthropic",
        _factory,
    )
    return captured


def _status_exc(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


async def test_system_messages_lifted_and_concatenated(monkeypatch):
    messages = _FakeMessages()
    _patch(monkeypatch, messages)
    convo = [
        ChatMessage(role="system", content="Jesteś asystentem."),
        ChatMessage(role="system", content="Bądź zwięzły."),
        ChatMessage(role="user", content="cześć"),
    ]

    await AnthropicProvider("sk-test", max_tokens=100).complete(convo, model="claude-x")

    assert messages.last_kwargs["system"] == "Jesteś asystentem.\n\nBądź zwięzły."
    assert messages.last_kwargs["messages"] == [{"role": "user", "content": "cześć"}]


async def test_no_system_omits_param(monkeypatch):
    messages = _FakeMessages()
    _patch(monkeypatch, messages)

    await AnthropicProvider("sk-test", max_tokens=100).complete(
        [ChatMessage(role="user", content="cześć")], model="claude-x"
    )

    assert "system" not in messages.last_kwargs


async def test_consecutive_same_role_merged_and_alternating(monkeypatch):
    messages = _FakeMessages()
    _patch(monkeypatch, messages)
    convo = [
        ChatMessage(role="user", content="a"),
        ChatMessage(role="user", content="b"),
        ChatMessage(role="assistant", content="x"),
        ChatMessage(role="assistant", content="y"),
        ChatMessage(role="user", content="c"),
    ]

    await AnthropicProvider("sk-test", max_tokens=100).complete(convo, model="claude-x")

    assert messages.last_kwargs["messages"] == [
        {"role": "user", "content": "a\n\nb"},
        {"role": "assistant", "content": "x\n\ny"},
        {"role": "user", "content": "c"},
    ]


async def test_max_tokens_passed_and_no_stream(monkeypatch):
    messages = _FakeMessages()
    captured = _patch(monkeypatch, messages)

    await AnthropicProvider("sk-test", max_tokens=1234).complete(
        [ChatMessage(role="user", content="cześć")], model="claude-x"
    )

    assert messages.last_kwargs["max_tokens"] == 1234
    assert messages.last_kwargs.get("stream") is None  # synchronous only
    assert captured["client_kwargs"]["max_retries"] == 0  # never retries


async def test_joins_text_blocks(monkeypatch):
    messages = _FakeMessages(result=_response("Dzień ", "dobry"))
    _patch(monkeypatch, messages)

    result = await AnthropicProvider("sk-test", max_tokens=100).complete(
        [ChatMessage(role="user", content="cześć")], model="claude-x"
    )

    assert result.content == "Dzień dobry"
    assert result.finish_reason == "stop"  # end_turn → "stop" (FR-003)
    assert result.provider == "anthropic"


@pytest.mark.parametrize(
    "stop_reason,expected",
    [("end_turn", "stop"), ("stop_sequence", "stop"), ("max_tokens", "length")],
)
async def test_stop_reason_normalized_to_openai_vocab(
    monkeypatch, stop_reason, expected
):
    messages = _FakeMessages(result=_response("ok", stop_reason=stop_reason))
    _patch(monkeypatch, messages)

    result = await AnthropicProvider("sk-test", max_tokens=100).complete(
        [ChatMessage(role="user", content="cześć")], model="claude-x"
    )

    assert result.finish_reason == expected


@pytest.mark.parametrize(
    "exc,kind",
    [
        (_status_exc(anthropic.RateLimitError, 429), "rate_limit"),
        (_status_exc(anthropic.AuthenticationError, 401), "auth"),
        (_status_exc(anthropic.PermissionDeniedError, 403), "auth"),
        (_status_exc(anthropic.NotFoundError, 404), "missing_model"),
        (
            anthropic.APIConnectionError(
                message="x",
                request=httpx.Request("POST", "https://api.anthropic.com/v1/x"),
            ),
            "unreachable",
        ),
        (
            anthropic.APITimeoutError(
                request=httpx.Request("POST", "https://api.anthropic.com/v1/x")
            ),
            "timeout",
        ),
    ],
)
async def test_sdk_exceptions_map_to_kind_without_retry(monkeypatch, exc, kind):
    messages = _FakeMessages(exc=exc)
    _patch(monkeypatch, messages)

    with pytest.raises(LLMProviderError) as excinfo:
        await AnthropicProvider("sk-test", max_tokens=100).complete(
            [ChatMessage(role="user", content="cześć")], model="claude-x"
        )

    assert excinfo.value.kind == kind
    assert messages.calls == 1  # called exactly once — no retry


async def test_missing_key_raises_auth_without_building_client(monkeypatch):
    built = {"called": False}

    def _factory(**kwargs):
        built["called"] = True
        return _FakeClient(_FakeMessages())

    monkeypatch.setattr(
        "gateway_api.llm_providers.anthropic_provider.anthropic.AsyncAnthropic",
        _factory,
    )

    with pytest.raises(LLMProviderError) as excinfo:
        await AnthropicProvider(None, max_tokens=100).complete(
            [ChatMessage(role="user", content="cześć")], model="claude-x"
        )

    assert excinfo.value.kind == "auth"
    assert "ANTHROPIC_API_KEY" in str(excinfo.value)
    assert built["called"] is False
