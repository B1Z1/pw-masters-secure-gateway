"""T014 — EvaluationClient: health gate + response-view parsing (mocked transport)."""

from __future__ import annotations

import httpx
import pytest

from gateway_eval.gateway_client.evaluation_client import (
    EvaluationClient,
    GatewayClientError,
)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/health":
        return httpx.Response(200, json={"status": "ok", "dependencies": {"redis": "ok"}})
    if path == "/v1/detect":
        return httpx.Response(
            200,
            json={"entities": [{"entity_type": "PERSON", "start": 0, "end": 3, "score": 0.9, "text": "Jan"}]},
        )
    if path == "/v1/pseudonymize":
        return httpx.Response(
            200, json={"pseudonymized_text": "X", "entities_replaced": [], "session_id": "s1"}
        )
    if path == "/v1/depseudonymize":
        return httpx.Response(200, json={"restored_text": "Jan", "session_id": "s1"})
    if path == "/v1/chat/completions":
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Jan"}, "finish_reason": "stop"}],
                "session_id": "s1",
                "input_anonymization": {"pseudonymized_content": "X", "replacements": []},
                "anonymization_meta": {"provider": "echo", "timing_ms": {"total": 4.0}},
            },
        )
    return httpx.Response(404, json={"detail": "not found"})


def _client() -> EvaluationClient:
    return EvaluationClient("http://test", transport=httpx.MockTransport(_handler))


async def test_health_gate_parses_status():
    async with _client() as client:
        health = await client.health()
        assert health.is_ok


async def test_detect_parses_spans():
    async with _client() as client:
        spans = await client.detect("Jan")
        assert spans[0].entity_type == "PERSON"
        assert (spans[0].start, spans[0].end) == (0, 3)


async def test_pseudonymize_and_depseudonymize_views():
    async with _client() as client:
        pseudo = await client.pseudonymize("Jan", "s1")
        assert pseudo.pseudonymized_text == "X"
        restored = await client.depseudonymize("X", "s1")
        assert restored.restored_text == "Jan"


async def test_chat_view_extracts_meta_and_answer():
    async with _client() as client:
        chat = await client.chat_completions("Jan", "s1", "echo/echo")
        assert chat.answer == "Jan"
        assert chat.pseudonymized_content == "X"
        assert chat.timing_ms["total"] == 4.0
        assert chat.provider == "echo"


async def test_error_status_raises():
    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "Redis unavailable", "session_id": "s1"})

    async with EvaluationClient("http://test", transport=httpx.MockTransport(fail), max_retries=0) as client:
        with pytest.raises(GatewayClientError) as caught:
            await client.detect("x")
        assert caught.value.status_code == 503
