"""POST /v1/chat/completions — round-trip, multi-turn, routing, errors.

Covers Epic 4 (round-trip, multi-turn, 400/503/504) and Epic 5 routing through the
``LLMRouter`` (unknown model → 400, no-model default → Ollama stripped, rate_limit
→ 429, auth → 503 naming the key, ollama/ edges). Uses a fakeredis-backed store, a
stubbed engine, and a provider dependency override so the whole flow runs offline.
Asserts no original PII reaches the provider or the logs (FR-024, Constitution VIII).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from gateway_api.llm_providers import LLMRouter, OpenAIProvider, get_llm_provider
from gateway_api.llm_providers.base import ChatMessage, LLMProvider, LLMProviderError
from gateway_api.pii_detection.dto import DetectedEntity


class _RecordingProvider(LLMProvider):
    """Captures the messages it receives; echoes the last user content by default."""

    def __init__(self, reply: str | None = None):
        self.received: list[ChatMessage] | None = None
        self._reply = reply

    async def complete(self, messages, *, model):
        self.received = messages
        if self._reply is not None:
            return self._reply
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return ""

    async def health_check(self):
        return True


class _FailingProvider(LLMProvider):
    def __init__(self, kind):
        self._kind = kind
        self.calls = 0

    async def complete(self, messages, *, model):
        self.calls += 1
        raise LLMProviderError("boom", kind=self._kind)

    async def health_check(self):
        return False


class _ModelRecordingProvider(LLMProvider):
    """Records the model + messages it was called with (Epic 5 routing tests)."""

    def __init__(self, reply="ok"):
        self.model = None
        self.received = None
        self.calls = 0
        self._reply = reply

    async def complete(self, messages, *, model):
        self.calls += 1
        self.model = model
        self.received = messages
        return self._reply

    async def health_check(self):
        return True


def _router(adapters, *, default_model="ollama/qwen2.5:3b") -> LLMRouter:
    """An LLMRouter whose per-prefix adapters are the given doubles."""
    return LLMRouter(
        {prefix: (lambda a=adapter: a) for prefix, adapter in adapters.items()},
        default_model=default_model,
    )


def _three(ollama=None, gpt=None, claude=None) -> dict:
    """A full prefix→double map; defaults are inert recording doubles."""
    return {
        "gpt-": gpt or _ModelRecordingProvider(),
        "claude-": claude or _ModelRecordingProvider(),
        "ollama/": ollama or _ModelRecordingProvider(),
    }


class _FakeEngine:
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
    """Patch the Redis gate, model readiness, and the pipeline's store/engine."""
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
def use_provider():
    from gateway_api.main import app

    def _set(provider):
        app.dependency_overrides[get_llm_provider] = lambda: provider

    yield _set
    app.dependency_overrides.pop(get_llm_provider, None)


async def test_round_trip_restores_and_hides_pii(client, chat_env, use_provider):
    _, set_engine = chat_env
    set_engine(
        [
            ("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {}),
            ("LOCATION", "Kraków", "Kraków", "nom", {}),
            ("PESEL", "90010112345", None, None, {"gender": "male"}),
        ]
    )
    provider = _RecordingProvider()
    use_provider(provider)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "Jan Kowalski, Kraków, PESEL 90010112345."}
            ]
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    answer = body["choices"][0]["message"]["content"]
    assert "Jan Kowalski" in answer
    assert "Kraków" in answer
    assert "90010112345" in answer

    # The provider only ever saw synthetic values.
    sent = provider.received[0].content
    assert "Jan Kowalski" not in sent
    assert "Kraków" not in sent
    assert "90010112345" not in sent


async def test_session_id_generated_when_absent(client, chat_env, use_provider):
    _, set_engine = chat_env
    set_engine([])
    use_provider(_RecordingProvider(reply="ok"))

    resp = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "cześć"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"]


async def test_empty_messages_returns_400(client, chat_env, use_provider):
    _, set_engine = chat_env
    set_engine([])
    use_provider(_RecordingProvider())

    resp = await client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 400
    assert resp.json()["session_id"]


async def test_non_user_last_message_returns_400(client, chat_env, use_provider):
    _, set_engine = chat_env
    set_engine([])
    use_provider(_RecordingProvider())

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "hej"},
                {"role": "assistant", "content": "no"},
            ]
        },
    )
    assert resp.status_code == 400
    assert resp.json()["session_id"]


async def test_multi_turn_repseudonymizes_full_history(client, chat_env, use_provider):
    store, set_engine = chat_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    provider = _RecordingProvider(reply="ok")
    use_provider(provider)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "multi",
            "messages": [
                {"role": "user", "content": "Kto to Jan Kowalski?"},
                {"role": "assistant", "content": "Jan Kowalski to najemca."},
                {"role": "user", "content": "Gdzie mieszka Jan Kowalski?"},
            ],
        },
    )
    assert resp.status_code == 200

    for message in provider.received:
        assert "Jan Kowalski" not in message.content

    mappings = await store.get_all_mappings("multi")
    fake = next(m["fake"] for m in mappings if m["original"] == "Jan Kowalski")
    assert all(fake in message.content for message in provider.received)


@pytest.mark.parametrize(
    "kind,status",
    [
        ("unreachable", 503),
        ("missing_model", 503),
        ("timeout", 504),
        ("rate_limit", 429),
        ("auth", 503),
    ],
)
async def test_provider_error_maps_to_status(
        client, chat_env, use_provider, kind, status
):
    _, set_engine = chat_env
    set_engine([])
    use_provider(_FailingProvider(kind))

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "err",
            "messages": [{"role": "user", "content": "hej"}],
        },
    )
    assert resp.status_code == status
    assert resp.json()["session_id"] == "err"


async def test_no_original_pii_in_logs(client, chat_env, use_provider, caplog):
    _, set_engine = chat_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    use_provider(_RecordingProvider())

    with caplog.at_level(logging.INFO, logger="gateway_api"):
        await client.post(
            "/v1/chat/completions",
            json={
                "session_id": "log",
                "messages": [{"role": "user", "content": "Jan Kowalski"}],
            },
        )
    assert "Kowalski" not in caplog.text


# --- Epic 5: routing through the LLMRouter + extended error taxonomy ---------


async def test_unknown_model_returns_400_and_dispatches_nothing(
        client, chat_env, use_provider
):
    """US2: an unrecognized model → 400 listing prefixes; nothing sent."""
    _, set_engine = chat_env
    set_engine([])
    adapters = _three()
    use_provider(_router(adapters))

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "u",
            "model": "mistral-large",
            "messages": [{"role": "user", "content": "hej"}],
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["session_id"] == "u"
    for prefix in ("gpt-", "claude-", "ollama/"):
        assert prefix in body["detail"]
    assert all(adapter.calls == 0 for adapter in adapters.values())


async def test_no_model_uses_default_and_routes_to_ollama_stripped(
        client, chat_env, use_provider, monkeypatch
):
    """US2: no model → configured default (ollama/...) → Ollama with prefix stripped."""
    _, set_engine = chat_env
    set_engine([])
    monkeypatch.setattr(
        "gateway_api.api.chat.get_settings",
        lambda: SimpleNamespace(default_model="ollama/qwen2.5:3b"),
    )
    ollama = _ModelRecordingProvider()
    use_provider(_router(_three(ollama=ollama)))

    resp = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "cześć"}]},  # no model field
    )
    assert resp.status_code == 200
    assert ollama.calls == 1
    assert ollama.model == "qwen2.5:3b"  # default resolved + "ollama/" stripped


async def test_rate_limit_returns_429_without_retry(client, chat_env, use_provider):
    """US5: an upstream rate limit → 429, the provider is called once (no retry)."""
    _, set_engine = chat_env
    set_engine([])
    failing = _FailingProvider("rate_limit")
    use_provider(failing)

    resp = await client.post(
        "/v1/chat/completions",
        json={"session_id": "rl", "messages": [{"role": "user", "content": "hej"}]},
    )
    assert resp.status_code == 429
    assert resp.json()["session_id"] == "rl"
    assert failing.calls == 1  # no retry at the endpoint


async def test_missing_key_returns_503_naming_key(client, chat_env, use_provider):
    """US5: routing to a provider with no key → 503 naming the missing key."""
    _, set_engine = chat_env
    set_engine([])
    use_provider(_router(_three(gpt=OpenAIProvider(None))))

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "k",
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hej"}],
        },
    )
    assert resp.status_code == 503
    body = resp.json()
    assert body["session_id"] == "k"
    assert "OPENAI_API_KEY" in body["detail"]


def test_startup_succeeds_without_keys():
    """US5: keys optional at startup — building the router needs no keys/clients."""
    get_llm_provider.cache_clear()
    try:
        provider = get_llm_provider()
        assert isinstance(provider, LLMRouter)
    finally:
        get_llm_provider.cache_clear()


async def test_ollama_routed_and_stripped_via_endpoint(
        client, chat_env, use_provider
):
    """US6: an ollama/ model reaches the Ollama adapter with the prefix stripped."""
    _, set_engine = chat_env
    set_engine([])
    ollama = _ModelRecordingProvider()
    use_provider(_router(_three(ollama=ollama)))

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "ollama/qwen2.5:3b",
            "messages": [{"role": "user", "content": "cześć"}],
        },
    )
    assert resp.status_code == 200
    assert ollama.model == "qwen2.5:3b"


async def test_ollama_unreachable_through_router_returns_503(
        client, chat_env, use_provider
):
    """US6: the reused Ollama edge cases still surface through the router."""
    _, set_engine = chat_env
    set_engine([])
    use_provider(_router(_three(ollama=_FailingProvider("unreachable"))))

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "o",
            "model": "ollama/qwen2.5:3b",
            "messages": [{"role": "user", "content": "cześć"}],
        },
    )
    assert resp.status_code == 503
    assert resp.json()["session_id"] == "o"


async def test_no_pii_reaches_provider_or_logs_on_routed_path(
        client, chat_env, use_provider, caplog
):
    """Polish/FR-024: the routed provider sees only synthetic data; logs carry none."""
    _, set_engine = chat_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    ollama = _ModelRecordingProvider(reply="ok")
    use_provider(_router(_three(ollama=ollama)))

    with caplog.at_level(logging.INFO, logger="gateway_api"):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "session_id": "pii",
                "model": "ollama/qwen2.5:3b",
                "messages": [{"role": "user", "content": "Jan Kowalski"}],
            },
        )
    assert resp.status_code == 200
    for message in ollama.received:
        assert "Kowalski" not in message.content
    assert "Kowalski" not in caplog.text
