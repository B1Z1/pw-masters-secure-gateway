"""LLM provider port (Epic 4, FR-016/FR-019, Constitution IV).

The pipeline and the chat endpoint depend ONLY on this interface — never on a
concrete provider — so adding a provider needs no pipeline change. ``ChatMessage``
is the OpenAI-compatible unit the pipeline pseudonymizes; ``LLMProviderError``
carries a ``kind`` discriminator the chat handler maps to 503/504.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

# kind → HTTP, mapped centrally in api/chat.py (Epic 5, research D6):
#   unreachable / missing_model / auth → 503; timeout → 504; rate_limit → 429;
#   unknown_model → 400 (raised by the router before any adapter call).
ProviderErrorKind = Literal[
    "unreachable",
    "missing_model",
    "timeout",
    "rate_limit",
    "auth",
    "unknown_model",
]

# The OpenAI finish-reason vocabulary this gateway exposes (Epic 6, FR-003). Real
# provider values are mapped here so the chat response is always one of these; a
# provider that cannot report one (e.g. the echo stub) yields "stop".
_FINISH_REASON_BY_RAW: dict[str, str] = {
    "stop": "stop",  # OpenAI / Ollama
    "length": "length",  # OpenAI / Ollama
    "end_turn": "stop",  # Anthropic
    "stop_sequence": "stop",  # Anthropic
    "max_tokens": "length",  # Anthropic
}


def normalize_finish_reason(raw: str | None) -> str:
    """Map a provider's raw finish reason to OpenAI vocabulary (Epic 6, D2).

    Single source of truth for the mapping: known values normalize to "stop"/
    "length"; anything else (including ``None``/missing) defaults to "stop".
    """
    return _FINISH_REASON_BY_RAW.get(raw or "", "stop")


class ChatMessage(BaseModel):
    """One OpenAI-compatible conversation message."""

    role: str
    content: str


@dataclass(frozen=True)
class CompletionResult:
    """The provider port's return value (Epic 6, FR-022).

    Replaces Epic 4/5's bare ``str``: the adapter self-reports the concrete
    ``provider`` name and a ``finish_reason`` already normalized to OpenAI
    vocabulary, so the chat endpoint stays provider-agnostic (Constitution IV).
    """

    content: str
    finish_reason: str  # normalized: "stop" | "length"
    provider: str  # "openai" | "anthropic" | "ollama" | "echo"


class LLMProviderError(Exception):
    """A provider failure with a readable message and an HTTP-mapping ``kind``."""

    def __init__(self, message: str, *, kind: ProviderErrorKind) -> None:
        super().__init__(message)
        self.kind: ProviderErrorKind = kind


class LLMProvider(abc.ABC):
    """Abstract provider: send a messages array, get assistant text back."""

    @abc.abstractmethod
    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        """Return the assistant reply, or raise ``LLMProviderError`` on failure."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Lightweight reachability probe (reserved for the future ``/health``)."""
