"""End-to-end smoke: REAL OpenAI/Anthropic adapters through the chat endpoint,
with the SDK client mocked (no key, no network).

Unlike test_chat_api.py (which routes through recording *doubles*), this exercises
the actual ``OpenAIProvider`` / ``AnthropicProvider`` classes — message building,
the Anthropic system-lift/merge conversion, and the pipeline round-trip — proving
the providers are correctly wired into the gateway. The mocked SDK echoes the last
(pseudonymized) user turn, so we can assert the provider saw only synthetic data
and the answer comes back with the originals restored.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from gateway_api.llm_providers import (
    AnthropicProvider,
    LLMRouter,
    OllamaProvider,
    OpenAIProvider,
    get_llm_provider,
)
from gateway_api.pii_detection.dto import DetectedEntity


class _FakeEngine:
    """Exact-surface detector for deterministic, offline pseudonymization."""

    def __init__(self, specs):
        self._specs = specs

    def detect(self, text):
        results = []
        for entity_type, value, lemma, case, metadata in self._specs:
            start = text.find(value)
            if start != -1:
                results.append(
                    DetectedEntity(
                        entity_type=entity_type,
                        start=start,
                        end=start + len(value),
                        score=1.0,
                        text=value,
                        lemma=lemma,
                        case=case,
                        metadata=metadata or {},
                    )
                )
        return results


@pytest.fixture
def chat_env(monkeypatch, make_store):
    """fakeredis-backed store + stubbed engine + open Redis gate + model ready."""
    store = make_store(seed=7)

    async def _redis_ok():
        return "ok"

    monkeypatch.setattr("gateway_api.main.check_redis", _redis_ok)
    monkeypatch.setattr("gateway_api.pii_detection.nlp.is_model_ready", lambda: True)
    monkeypatch.setattr(
        "gateway_api.pipeline.anonymization_pipeline.get_mapping_store", lambda: store
    )

    def _set_engine(specs):
        monkeypatch.setattr(
            "gateway_api.pipeline.anonymization_pipeline.get_engine",
            lambda: _FakeEngine(specs),
        )

    return store, _set_engine


@pytest.fixture
def use_real_router():
    """Override the dependency with a router wired to the REAL adapters."""
    from gateway_api.main import app

    router = LLMRouter(
        {
            "gpt-": lambda: OpenAIProvider("sk-test"),
            "claude-": lambda: AnthropicProvider("sk-test", max_tokens=1024),
            "ollama/": lambda: OllamaProvider("http://unused", 1.0),
        },
        default_model="ollama/qwen2.5:3b",
    )
    app.dependency_overrides[get_llm_provider] = lambda: router
    yield
    app.dependency_overrides.pop(get_llm_provider, None)


def _last_user(messages):
    return next(m["content"] for m in reversed(messages) if m["role"] == "user")


def _patch_openai_sdk(monkeypatch, captured):
    """Mock openai.AsyncOpenAI to echo the last user turn (synthetic) back."""

    class _Completions:
        async def create(self, **kwargs):
            captured["create"] = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=_last_user(kwargs["messages"])),
                        finish_reason="stop",
                    )
                ]
            )

    class _Client:
        def __init__(self, **client_kwargs):
            captured["client"] = client_kwargs
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(
        "gateway_api.llm_providers.openai_provider.openai.AsyncOpenAI", _Client
    )


def _patch_anthropic_sdk(monkeypatch, captured):
    """Mock anthropic.AsyncAnthropic to echo the last user turn (synthetic) back."""

    class _Messages:
        async def create(self, **kwargs):
            captured["create"] = kwargs
            reply = _last_user(kwargs["messages"])
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)])

    class _Client:
        def __init__(self, **client_kwargs):
            captured["client"] = client_kwargs
            self.messages = _Messages()

    monkeypatch.setattr(
        "gateway_api.llm_providers.anthropic_provider.anthropic.AsyncAnthropic", _Client
    )


_PII_SPECS = [
    ("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {}),
    ("LOCATION", "Kraków", "Kraków", "nom", {}),
    ("PESEL", "90010112345", None, None, {"gender": "male"}),
]


async def test_openai_provider_round_trip_via_mocked_sdk(
    client, chat_env, use_real_router, monkeypatch
):
    _, set_engine = chat_env
    set_engine(_PII_SPECS)
    captured: dict = {}
    _patch_openai_sdk(monkeypatch, captured)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": "Najemcą jest Jan Kowalski z Kraków, PESEL 90010112345.",
                }
            ],
        },
    )

    assert resp.status_code == 200
    answer = resp.json()["choices"][0]["message"]["content"]
    sent = _last_user(captured["create"]["messages"])

    print("\n=== OpenAI (gpt-4o) ===")
    print("  client built with :", captured["client"])  # max_retries=0
    print("  model sent to SDK :", captured["create"]["model"])
    print("  → sent to provider:", sent)
    print("  ← restored answer :", answer)

    # Originals restored for the caller…
    assert "Jan Kowalski" in answer and "Kraków" in answer and "90010112345" in answer
    # …but the provider only ever saw synthetic data.
    assert "Jan Kowalski" not in sent and "90010112345" not in sent
    assert captured["create"]["model"] == "gpt-4o"
    assert captured["client"]["max_retries"] == 0
    assert "stream" not in captured["create"]


async def test_anthropic_provider_conversion_and_round_trip_via_mocked_sdk(
    client, chat_env, use_real_router, monkeypatch
):
    _, set_engine = chat_env
    set_engine(_PII_SPECS)
    captured: dict = {}
    _patch_anthropic_sdk(monkeypatch, captured)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-3-5-sonnet",
            "messages": [
                {"role": "system", "content": "Jesteś prawnikiem."},
                {"role": "user", "content": "Kim jest Jan Kowalski?"},
                {"role": "user", "content": "Czy Jan Kowalski jest z Kraków?"},
            ],
        },
    )

    assert resp.status_code == 200
    answer = resp.json()["choices"][0]["message"]["content"]
    create = captured["create"]
    outgoing = create["messages"]

    print("\n=== Anthropic (claude-3-5-sonnet) ===")
    print("  client built with :", captured["client"])  # max_retries=0
    print("  system (lifted)   :", create.get("system"))
    print("  max_tokens        :", create["max_tokens"])
    print("  outgoing turns    :", outgoing)
    print("  ← restored answer :", answer)

    # System lifted to the top-level param; the two consecutive user turns merged.
    assert create["system"] == "Jesteś prawnikiem."
    assert create["max_tokens"] == 1024
    assert [m["role"] for m in outgoing] == ["user"]  # merged into one user turn
    # No original PII reached Anthropic…
    assert "Jan Kowalski" not in outgoing[0]["content"]
    assert "Kraków" not in outgoing[0]["content"]
    # …and the answer has the originals restored.
    assert "Jan Kowalski" in answer and "Kraków" in answer
    assert captured["client"]["max_retries"] == 0
