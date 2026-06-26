"""Async HTTP client against the live gateway (contracts/consumed-endpoints.md).

A thin client over the public surface. The parsed response views are the
*predictions under test* — never ground truth (anti-circularity, D1). The harness
uses ``pseudonymized_text`` / ``input_anonymization.pseudonymized_content`` only as
the outbound text to audit for leaks, and never treats ``entities_replaced`` as the
detection answer key.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import httpx
from pydantic import BaseModel


class DetectedSpan(BaseModel):
    entity_type: str
    start: int
    end: int
    score: float = 1.0
    text: str = ""


class HealthView(BaseModel):
    status: str
    dependencies: dict[str, str] = {}

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


class PseudonymizeView(BaseModel):
    pseudonymized_text: str
    session_id: str
    entities_replaced: list[dict] = []

    @property
    def fake_values(self) -> list[str]:
        return [
            item.get("fake", "")
            for item in self.entities_replaced
            if item.get("fake")
        ]


class DepseudonymizeView(BaseModel):
    restored_text: str
    session_id: str


class ChatView(BaseModel):
    answer: str
    session_id: str
    pseudonymized_content: str
    timing_ms: dict[str, float] = {}
    provider: str = ""
    fake_values: list[str] = []


class GatewayClientError(RuntimeError):
    """Raised on a non-retryable gateway error (parsed status + detail)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"gateway HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class EvaluationClient:
    """One client per run; open via ``async with EvaluationClient(...) as client``."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        # ``transport`` is for tests (httpx.MockTransport / ASGITransport); production
        # leaves it None so httpx uses the network stack.
        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout_s, transport=transport
        )

    async def __aenter__(self) -> EvaluationClient:
        return self

    async def __aexit__(self, *exception_info: object) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(path, json=payload)
            except httpx.TransportError as transport_error:
                last_error = transport_error
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail = _extract_detail(response)
                raise GatewayClientError(response.status_code, detail)
            return response.json()
        raise GatewayClientError(503, f"transport error: {last_error}")

    # --- endpoints ---------------------------------------------------------

    async def health(self) -> HealthView:
        # An unreachable/malformed gateway is reported as not-ok (never raised), so the
        # harness fails gracefully rather than crashing (FR-005).
        try:
            response = await self._client.get("/health")
            return HealthView.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            return HealthView(status="unreachable", dependencies={})

    async def detect(self, text: str) -> list[DetectedSpan]:
        body = await self._post("/v1/detect", {"text": text})
        return [DetectedSpan.model_validate(item) for item in body.get("entities", [])]

    async def pseudonymize(self, text: str, session_id: str) -> PseudonymizeView:
        body = await self._post(
            "/v1/pseudonymize", {"text": text, "session_id": session_id}
        )
        return PseudonymizeView.model_validate(body)

    async def depseudonymize(self, text: str, session_id: str) -> DepseudonymizeView:
        body = await self._post(
            "/v1/depseudonymize", {"text": text, "session_id": session_id}
        )
        return DepseudonymizeView.model_validate(body)

    async def chat_completions(
        self, text: str, session_id: str, model: str
    ) -> ChatView:
        body = await self._post(
            "/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": text}],
                "session_id": session_id,
                "model": model,
            },
        )
        choices = body.get("choices") or [{}]
        answer = choices[0].get("message", {}).get("content", "")
        input_anonymization = body.get("input_anonymization", {})
        meta = body.get("anonymization_meta", {})
        replacements = input_anonymization.get("replacements", []) or []
        return ChatView(
            answer=answer,
            session_id=body.get("session_id", session_id),
            pseudonymized_content=input_anonymization.get("pseudonymized_content", ""),
            timing_ms=meta.get("timing_ms", {}) or {},
            provider=meta.get("provider", ""),
            fake_values=[
                item.get("fake", "") for item in replacements if item.get("fake")
            ],
        )

    async def delete_session(self, session_id: str) -> None:
        # Cleanup is best-effort — TTL expiry is the backstop (D6).
        with contextlib.suppress(httpx.HTTPError):
            await self._client.delete(f"/v1/sessions/{session_id}")


def _extract_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except Exception:  # noqa: BLE001 — non-JSON error body
        return response.text
