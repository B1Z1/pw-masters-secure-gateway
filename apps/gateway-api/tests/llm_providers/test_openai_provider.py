"""OpenAIProvider — native pass-through, truncation, error→kind, no retry (US4).

The async OpenAI client is mocked (no network, no key needed beyond a dummy).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from gateway_api.llm_providers.base import ChatMessage, LLMProviderError
from gateway_api.llm_providers.openai_provider import OpenAIProvider

_MESSAGES = [
    ChatMessage(role="system", content="Jesteś asystentem."),
    ChatMessage(role="user", content="cześć"),
]


def _response(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content), finish_reason=finish_reason
            )
        ]
    )


class _FakeCompletions:
    def __init__(self, *, result=None, exc=None):
        self._result = result
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
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def _patch(monkeypatch, completions):
    captured: dict = {}

    def _factory(**kwargs):
        captured["client_kwargs"] = kwargs
        return _FakeClient(completions)

    monkeypatch.setattr(
        "gateway_api.llm_providers.openai_provider.openai.AsyncOpenAI", _factory
    )
    return captured


def _status_exc(cls, status):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


async def test_native_passthrough_no_conversion_no_stream(monkeypatch):
    completions = _FakeCompletions(result=_response("ok"))
    captured = _patch(monkeypatch, completions)

    result = await OpenAIProvider("sk-test").complete(_MESSAGES, model="gpt-4o")

    assert result == "ok"
    # Native shape: messages passed through unchanged, system stays first.
    assert completions.last_kwargs["messages"] == [
        {"role": "system", "content": "Jesteś asystentem."},
        {"role": "user", "content": "cześć"},
    ]
    assert completions.last_kwargs["model"] == "gpt-4o"
    assert completions.last_kwargs.get("stream") is None  # synchronous only
    assert captured["client_kwargs"]["max_retries"] == 0  # never retries


async def test_length_truncation_warns_and_returns_partial(monkeypatch, caplog):
    completions = _FakeCompletions(result=_response("partial answer", "length"))
    _patch(monkeypatch, completions)

    with caplog.at_level(logging.WARNING, logger="gateway_api"):
        result = await OpenAIProvider("sk-test").complete(_MESSAGES, model="gpt-4o")

    assert result == "partial answer"  # partial content still returned
    assert "truncated" in caplog.text
    assert "partial answer" not in caplog.text  # content is never logged


@pytest.mark.parametrize(
    "exc,kind",
    [
        (_status_exc(openai.RateLimitError, 429), "rate_limit"),
        (_status_exc(openai.AuthenticationError, 401), "auth"),
        (_status_exc(openai.PermissionDeniedError, 403), "auth"),
        (_status_exc(openai.NotFoundError, 404), "missing_model"),
        (
            openai.APIConnectionError(
                message="x",
                request=httpx.Request("POST", "https://api.openai.com/v1/x"),
            ),
            "unreachable",
        ),
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.com/v1/x")
            ),
            "timeout",
        ),
    ],
)
async def test_sdk_exceptions_map_to_kind_without_retry(monkeypatch, exc, kind):
    completions = _FakeCompletions(exc=exc)
    _patch(monkeypatch, completions)

    with pytest.raises(LLMProviderError) as excinfo:
        await OpenAIProvider("sk-test").complete(_MESSAGES, model="gpt-4o")

    assert excinfo.value.kind == kind
    assert completions.calls == 1  # called exactly once — no retry


async def test_missing_key_raises_auth_without_building_client(monkeypatch):
    built = {"called": False}

    def _factory(**kwargs):
        built["called"] = True
        return _FakeClient(_FakeCompletions(result=_response("ok")))

    monkeypatch.setattr(
        "gateway_api.llm_providers.openai_provider.openai.AsyncOpenAI", _factory
    )

    with pytest.raises(LLMProviderError) as excinfo:
        await OpenAIProvider(None).complete(_MESSAGES, model="gpt-4o")

    assert excinfo.value.kind == "auth"
    assert "OPENAI_API_KEY" in str(excinfo.value)
    assert built["called"] is False  # no client constructed when the key is missing
