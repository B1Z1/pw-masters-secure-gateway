"""OllamaProvider error→kind mapping and parsing (US4), mocked httpx — no network."""

from __future__ import annotations

import httpx
import pytest

from gateway_api.llm_providers.base import ChatMessage, LLMProviderError
from gateway_api.llm_providers.ollama_provider import OllamaProvider

_MESSAGES = [ChatMessage(role="user", content="cześć")]


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *, exc=None, response=None):
        self._exc = exc
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None):
        if self._exc is not None:
            raise self._exc
        return self._response

    async def get(self, url):
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_client(monkeypatch, *, exc=None, response=None):
    monkeypatch.setattr(
        "gateway_api.llm_providers.ollama_provider.httpx.AsyncClient",
        lambda *args, **kwargs: _FakeClient(exc=exc, response=response),
    )


@pytest.fixture
def provider():
    return OllamaProvider("http://ollama:11434", timeout=5.0)


async def test_complete_parses_message_content(provider, monkeypatch):
    _patch_client(
        monkeypatch,
        response=_FakeResponse(
            200, {"message": {"content": "Dzień dobry"}, "done_reason": "stop"}
        ),
    )
    result = await provider.complete(_MESSAGES, model="m")
    assert result.content == "Dzień dobry"
    assert result.finish_reason == "stop"
    assert result.provider == "ollama"


async def test_complete_missing_done_reason_defaults_to_stop(provider, monkeypatch):
    _patch_client(
        monkeypatch, response=_FakeResponse(200, {"message": {"content": "ok"}})
    )
    result = await provider.complete(_MESSAGES, model="m")
    assert result.finish_reason == "stop"  # absent done_reason → "stop" (FR-003)


async def test_complete_length_done_reason_normalizes(provider, monkeypatch):
    _patch_client(
        monkeypatch,
        response=_FakeResponse(
            200, {"message": {"content": "cut"}, "done_reason": "length"}
        ),
    )
    result = await provider.complete(_MESSAGES, model="m")
    assert result.finish_reason == "length"


async def test_connect_error_maps_to_unreachable(provider, monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ConnectError("refused"))
    with pytest.raises(LLMProviderError) as excinfo:
        await provider.complete(_MESSAGES, model="m")
    assert excinfo.value.kind == "unreachable"


async def test_read_timeout_maps_to_timeout(provider, monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ReadTimeout("slow"))
    with pytest.raises(LLMProviderError) as excinfo:
        await provider.complete(_MESSAGES, model="m")
    assert excinfo.value.kind == "timeout"


async def test_404_maps_to_missing_model(provider, monkeypatch):
    _patch_client(
        monkeypatch, response=_FakeResponse(404, text="model 'x' not found")
    )
    with pytest.raises(LLMProviderError) as excinfo:
        await provider.complete(_MESSAGES, model="x")
    assert excinfo.value.kind == "missing_model"


async def test_health_check_true_when_reachable(provider, monkeypatch):
    _patch_client(monkeypatch, response=_FakeResponse(200, {"models": []}))
    assert await provider.health_check() is True


async def test_health_check_false_when_down(provider, monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ConnectError("down"))
    assert await provider.health_check() is False
