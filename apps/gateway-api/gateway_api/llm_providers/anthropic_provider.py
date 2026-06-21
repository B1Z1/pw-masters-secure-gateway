"""Anthropic adapter (Epic 5, FR-007..FR-010).

Serves models whose name starts with ``claude-``. Anthropic's message rules
differ from OpenAI's, so the adapter converts the OpenAI-shaped messages:
``system`` content is lifted into Anthropic's separate top-level ``system`` field
(multiple system messages concatenated; the field omitted when there is none),
the remaining turns must begin with a user turn and alternate user/assistant (two
consecutive same-role messages are merged into one), and every call carries an
explicit ``max_tokens`` from configuration. The async client is built lazily (only
when the key is present) and cached with ``max_retries=0`` so the adapter never
retries (FR-020); SDK exceptions map to ``LLMProviderError`` kinds.
"""

from __future__ import annotations

import anthropic

from .base import (
    ChatMessage,
    CompletionResult,
    LLMProvider,
    LLMProviderError,
    normalize_finish_reason,
)

_SEPARATOR = "\n\n"


def _split_system_and_turns(
    messages: list[ChatMessage],
) -> tuple[str | None, list[dict]]:
    """Lift+concatenate system content; merge consecutive same-role turns.

    Returns ``(system, turns)`` where ``system`` is ``None`` when there is no
    system content (so the caller omits the parameter), and ``turns`` is the
    user/assistant history with consecutive same-role messages merged.
    """
    system_parts = [
        message.content for message in messages if message.role == "system"
    ]
    system = _SEPARATOR.join(system_parts) if system_parts else None

    turns: list[dict] = []
    for message in messages:
        if message.role == "system":
            continue
        if turns and turns[-1]["role"] == message.role:
            turns[-1]["content"] += _SEPARATOR + message.content
        else:
            turns.append({"role": message.role, "content": message.content})
    return system, turns


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None, max_tokens: int) -> None:
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._client: anthropic.AsyncAnthropic | None = None

    def _ensure_client(self) -> anthropic.AsyncAnthropic:
        if not self._api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured", kind="auth")
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key, max_retries=0
            )
        return self._client

    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        client = self._ensure_client()
        system, turns = _split_system_and_turns(messages)

        request: dict = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": turns,
        }
        if system is not None:
            request["system"] = system

        try:
            response = await client.messages.create(**request)
        except anthropic.APITimeoutError as exc:  # subclass of APIConnectionError
            raise LLMProviderError(str(exc), kind="timeout") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMProviderError(str(exc), kind="unreachable") from exc
        except anthropic.RateLimitError as exc:
            raise LLMProviderError(str(exc), kind="rate_limit") from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise LLMProviderError(
                "Anthropic rejected the credentials (check ANTHROPIC_API_KEY)",
                kind="auth",
            ) from exc
        except anthropic.NotFoundError as exc:
            raise LLMProviderError(str(exc), kind="missing_model") from exc

        content = "".join(
            block.text for block in response.content if block.type == "text"
        )
        # Anthropic reports stop_reason (end_turn/max_tokens/stop_sequence); a
        # mock may omit it → getattr default None → normalized to "stop".
        return CompletionResult(
            content=content,
            finish_reason=normalize_finish_reason(
                getattr(response, "stop_reason", None)
            ),
            provider="anthropic",
        )

    async def health_check(self) -> bool:
        return bool(self._api_key)
