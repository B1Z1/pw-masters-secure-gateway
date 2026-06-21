"""Deterministic, network-free provider for tests (Epic 4, FR-018).

Returns a fixed transform of the conversation (the last user message's content)
so pipeline round-trip tests assert restoration without contacting a model. As a
stub it cannot report a finish reason, so it yields ``"stop"`` (Epic 6, FR-003).
"""

from __future__ import annotations

from .base import ChatMessage, CompletionResult, LLMProvider


class EchoProvider(LLMProvider):
    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        content = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == "user"
            ),
            messages[-1].content if messages else "",
        )
        return CompletionResult(content=content, finish_reason="stop", provider="echo")

    async def health_check(self) -> bool:
        return True
