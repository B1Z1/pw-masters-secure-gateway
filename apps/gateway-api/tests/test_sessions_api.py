"""GET/DELETE /v1/sessions/{id} — statistics, reset, and the 404 matrix (Epic 6, US2).

Drives a real chat turn (recording double + fakeredis) to populate the session,
then reads/deletes it. The session endpoints and the chat pipeline are pointed at
the SAME fakeredis-backed store so the turn's mappings are visible to the GET.
"""

from __future__ import annotations

import pytest

from gateway_api.llm_providers import get_llm_provider
from gateway_api.llm_providers.base import CompletionResult, LLMProvider
from gateway_api.pii_detection.dto import DetectedEntity


class _RecordingProvider(LLMProvider):
    async def complete(self, messages, *, model):
        content = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        return CompletionResult(
            content=content, finish_reason="stop", provider="ollama"
        )

    async def health_check(self):
        return True


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
def sessions_env(monkeypatch, make_store):
    """One fakeredis store shared by the chat pipeline AND the session endpoints."""
    store = make_store(seed=7)

    async def _redis_ok():
        return "ok"

    monkeypatch.setattr("gateway_api.main.check_redis", _redis_ok)
    monkeypatch.setattr("gateway_api.pii_detection.nlp.is_model_ready", lambda: True)
    monkeypatch.setattr(
        "gateway_api.pipeline.anonymization_pipeline.get_mapping_store", lambda: store
    )
    monkeypatch.setattr("gateway_api.api.sessions.get_mapping_store", lambda: store)

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


async def _chat(client, session_id, content):
    return await client.post(
        "/v1/chat/completions",
        json={
            "session_id": session_id,
            "messages": [{"role": "user", "content": content}],
        },
    )


async def test_get_session_returns_statistics(client, sessions_env, use_provider):
    _, set_engine = sessions_env
    set_engine(
        [
            ("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {}),
            ("PERSON", "Anna Nowak", "Anna Nowak", "nom", {}),
            ("PESEL", "90010112345", None, None, {"gender": "male"}),
        ]
    )
    use_provider(_RecordingProvider())

    assert (
        await _chat(client, "s", "Jan Kowalski i Anna Nowak, PESEL 90010112345.")
    ).status_code == 200

    resp = await client.get("/v1/sessions/s")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s"
    assert body["entity_count"] == 3
    assert body["entities_by_type"] == {"PERSON": 2, "PESEL": 1}
    assert body["message_count"] == 1
    assert body["ttl_remaining_seconds"] > 0
    assert body["created_at"] and body["last_activity"]


async def test_delete_resets_then_404(client, sessions_env, use_provider):
    _, set_engine = sessions_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    use_provider(_RecordingProvider())
    await _chat(client, "d", "Jan Kowalski")

    assert (await client.delete("/v1/sessions/d")).status_code == 200
    assert (await client.get("/v1/sessions/d")).status_code == 404
    assert (await client.delete("/v1/sessions/d")).status_code == 404  # already gone


async def test_unknown_session_is_404(client, sessions_env):
    _, set_engine = sessions_env
    set_engine([])
    assert (await client.get("/v1/sessions/nope")).status_code == 404
    assert (await client.delete("/v1/sessions/nope")).status_code == 404


async def test_session_with_no_pii_is_404(client, sessions_env, use_provider):
    """A successful turn that detected no PII leaves no stored state → 404 (FR-021)."""
    _, set_engine = sessions_env
    set_engine([])
    use_provider(_RecordingProvider())
    assert (await _chat(client, "empty", "cześć")).status_code == 200

    assert (await client.get("/v1/sessions/empty")).status_code == 404
    assert (await client.delete("/v1/sessions/empty")).status_code == 404
