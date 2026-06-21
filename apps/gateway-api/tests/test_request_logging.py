"""Logging & metrics middleware — one PII-free JSON line per request (Epic 6, US4).

Captures stdout (where the middleware emits) and audits the line against the known
PII / fake values. Network-free: fakeredis + a recording double.
"""

from __future__ import annotations

import json

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
def logging_env(monkeypatch, make_store):
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


def _log_lines_for(capsys, endpoint):
    lines = []
    for line in capsys.readouterr().out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("endpoint") == endpoint:
            lines.append(record)
    return lines


async def test_one_structured_line_with_required_fields(
        client, logging_env, use_provider, capsys
):
    _, set_engine = logging_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    use_provider(_RecordingProvider())

    await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "L",
            "messages": [{"role": "user", "content": "Jan Kowalski"}],
        },
    )

    lines = _log_lines_for(capsys, "/v1/chat/completions")
    assert len(lines) == 1  # exactly one structured line for the request (FR-013)
    record = lines[0]
    assert record["session_id"] == "L"
    assert record["provider"] == "ollama"
    assert record["model"] == "ollama/qwen2.5:3b"
    assert record["entities_detected"] == {"PERSON": 1}
    assert set(record["timing_ms"]) == {
        "ner_analysis",
        "fake_generation",
        "redis_write",
        "llm_request",
        "deanonymization",
        "total",
    }
    assert record["timestamp"]


async def test_log_line_has_no_pii_content_or_fakes(
        client, logging_env, use_provider, capsys
):
    _, set_engine = logging_env
    set_engine([("PERSON", "Jan Kowalski", "Jan Kowalski", "nom", {})])
    use_provider(_RecordingProvider())

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "session_id": "L",
            "messages": [{"role": "user", "content": "Jan Kowalski"}],
        },
    )
    fake = resp.json()["input_anonymization"]["replacements"][0]["fake"]

    out = capsys.readouterr().out
    chat_line = next(
        line
        for line in out.splitlines()
        if line.strip().startswith("{")
        and json.loads(line).get("endpoint") == "/v1/chat/completions"
    )
    assert "Kowalski" not in chat_line  # no original PII
    assert fake not in chat_line  # no fake value
    assert "Jan Kowalski" not in chat_line


async def test_endpoint_is_route_template_not_path_value(
        client, logging_env, capsys
):
    """A path with a session_id logs the TEMPLATE, never the id value (FR-016)."""
    await client.get("/v1/sessions/secret-session-id-123")  # 404 (no state) — fine

    out = capsys.readouterr().out
    assert "/v1/sessions/{session_id}" in out
    assert "secret-session-id-123" not in out


async def test_logging_failure_does_not_break_request(
        client, logging_env, use_provider, monkeypatch, capsys
):
    _, set_engine = logging_env
    set_engine([])
    use_provider(_RecordingProvider())

    def _boom(*args, **kwargs):
        raise RuntimeError("emit failed")

    monkeypatch.setattr(
        "gateway_api.observability.request_logging._emit_log_line", _boom
    )

    resp = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "cześć"}]},
    )
    assert resp.status_code == 200  # the request is unaffected (FR-017)
    assert "request-logging failed" in capsys.readouterr().err
