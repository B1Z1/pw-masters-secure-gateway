"""LLM provider port (Epic 4, FR-016/FR-019, Constitution IV).

The pipeline and the chat endpoint depend ONLY on this interface — never on a
concrete provider — so adding a provider needs no pipeline change. ``ChatMessage``
is the OpenAI-compatible unit the pipeline pseudonymizes; ``LLMProviderError``
carries a ``kind`` discriminator the chat handler maps to 503/504.
"""

from __future__ import annotations

import abc
from typing import Literal

from pydantic import BaseModel

# unreachable / missing_model → 503; timeout → 504 (research D6).
ProviderErrorKind = Literal["unreachable", "missing_model", "timeout"]


class ChatMessage(BaseModel):
    """One OpenAI-compatible conversation message."""

    role: str
    content: str


class LLMProviderError(Exception):
    """A provider failure with a readable message and an HTTP-mapping ``kind``."""

    def __init__(self, message: str, *, kind: ProviderErrorKind) -> None:
        super().__init__(message)
        self.kind: ProviderErrorKind = kind


class LLMProvider(abc.ABC):
    """Abstract provider: send a messages array, get assistant text back."""

    @abc.abstractmethod
    async def complete(self, messages: list[ChatMessage], *, model: str) -> str:
        """Return the assistant reply, or raise ``LLMProviderError`` on failure."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Lightweight reachability probe (reserved for the future ``/health``)."""
