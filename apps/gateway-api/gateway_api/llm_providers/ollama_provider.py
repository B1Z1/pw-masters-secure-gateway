"""Local Ollama REST adapter (Epic 4, FR-017/FR-022/FR-025, research D7).

``POST {OLLAMA_BASE_URL}/api/chat`` with ``stream=false`` (Constitution V — the
full answer is received before de-pseudonymization). Connection failures, a
missing model, and timeouts map to ``LLMProviderError`` kinds the chat handler
turns into 503/504.
"""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def complete(self, messages: list[ChatMessage], *, model: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise LLMProviderError(
                f"Ollama unreachable at {self._base_url}", kind="unreachable"
            ) from exc
        except (httpx.ReadTimeout, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"Ollama timed out after {self._timeout}s", kind="timeout"
            ) from exc

        if self._is_missing_model(response):
            raise LLMProviderError(
                f"Ollama model '{model}' not found", kind="missing_model"
            )

        if response.status_code >= 400:
            raise LLMProviderError(
                f"Ollama returned HTTP {response.status_code}", kind="unreachable"
            )

        return response.json()["message"]["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/api/tags")
        except httpx.HTTPError:
            return False

        return response.status_code < 400

    @staticmethod
    def _is_missing_model(response: httpx.Response) -> bool:
        if response.status_code == 404:
            return True
        if response.status_code >= 400:
            body = response.text.lower()
            return "model" in body and "not found" in body
        return False
