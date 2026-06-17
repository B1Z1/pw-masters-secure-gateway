"""Deterministic, network-free provider for tests (Epic 4, FR-018).

Returns a fixed transform of the conversation (the last user message's content)
so pipeline round-trip tests assert restoration without contacting a model.
"""

from __future__ import annotations

from .base import ChatMessage, LLMProvider


class EchoProvider(LLMProvider):
    async def complete(self, messages: list[ChatMessage], *, model: str) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content

        return messages[-1].content if messages else ""

    async def health_check(self) -> bool:
        return True
