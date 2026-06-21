"""OpenAI adapter (Epic 5, FR-003..FR-006).

Serves models whose name starts with ``gpt-``. OpenAI's message format is the
system's native shape, so there is NO conversion — a system message is passed
through as the first message. A length-truncated answer (``finish_reason ==
"length"``) is logged as a warning and the partial content is still returned. A
deprecated/unknown model surfaces the provider's own error. The async client is
built lazily (only when the key is present) and cached with ``max_retries=0`` so
the adapter never retries (FR-020); SDK exceptions map to ``LLMProviderError``
kinds the chat handler turns into HTTP statuses.
"""

from __future__ import annotations

import logging

import openai

from .base import (
    ChatMessage,
    CompletionResult,
    LLMProvider,
    LLMProviderError,
    normalize_finish_reason,
)

logger = logging.getLogger("gateway_api")


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key
        self._client: openai.AsyncOpenAI | None = None

    def _ensure_client(self) -> openai.AsyncOpenAI:
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured", kind="auth")
        if self._client is None:
            # max_retries=0: the adapter never retries (FR-020); a rate limit is
            # surfaced to the caller unchanged.
            self._client = openai.AsyncOpenAI(api_key=self._api_key, max_retries=0)
        return self._client

    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        client = self._ensure_client()
        # Native shape — no conversion; a system message stays the first message.
        payload = [
            {"role": message.role, "content": message.content} for message in messages
        ]

        try:
            response = await client.chat.completions.create(
                model=model, messages=payload
            )
        except openai.APITimeoutError as exc:  # subclass of APIConnectionError
            raise LLMProviderError(str(exc), kind="timeout") from exc
        except openai.APIConnectionError as exc:
            raise LLMProviderError(str(exc), kind="unreachable") from exc
        except openai.RateLimitError as exc:
            raise LLMProviderError(str(exc), kind="rate_limit") from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise LLMProviderError(
                "OpenAI rejected the credentials (check OPENAI_API_KEY)", kind="auth"
            ) from exc
        except openai.NotFoundError as exc:
            # Deprecated/unknown model — surface the provider's own error (FR-006).
            raise LLMProviderError(str(exc), kind="missing_model") from exc

        choice = response.choices[0]
        if choice.finish_reason == "length":
            # Truncated by the token limit — warn (no content logged) and still
            # return the partial answer (FR-005, Constitution VIII).
            logger.warning(
                "openai answer truncated finish_reason=length model=%s", model
            )
        return CompletionResult(
            content=choice.message.content or "",
            finish_reason=normalize_finish_reason(choice.finish_reason),
            provider="openai",
        )

    async def health_check(self) -> bool:
        return bool(self._api_key)
