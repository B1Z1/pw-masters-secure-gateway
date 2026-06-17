"""POST /v1/chat/completions — round-trip, multi-turn, errors (US1/US2/US4).

Uses a fakeredis-backed store, a stubbed engine, and a provider dependency
override so the whole flow runs offline. Asserts no original PII reaches the
provider or the logs (FR-024, Constitution VIII).
"""

from __future__ import annotations

import logging

import pytest

from gateway_api.llm_providers import get_llm_provider
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

    async def complete(self, messages, *, model):
        raise LLMProviderError("boom", kind=self._kind)

    async def health_check(self):
        return False


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
    [("unreachable", 503), ("missing_model", 503), ("timeout", 504)],
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
