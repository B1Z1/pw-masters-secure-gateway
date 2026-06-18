"""Epic 4 chat endpoint — the first end-to-end LLM round-trip (FR-020..FR-023).

``POST /v1/chat/completions`` (OpenAI-compatible in shape, minimal in content):
pseudonymize EVERY message → call the LLM with synthetic data only → restore the
originals in the answer. NOT gate-exempt — it needs Redis, so the Epic 1
middleware 503s it when Redis is down.

Validation that needs no LLM happens first (400). Provider failures map to
503/504 and preserve the session_id. Logs carry session_id + counts/status only,
never message content/originals/fakes (Constitution VIII, FR-024).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import get_settings
from ..llm_providers import LLMProvider, LLMProviderError, get_llm_provider
from ..llm_providers.base import ChatMessage, ProviderErrorKind
from ..pii_detection import nlp
from ..pipeline.anonymization_pipeline import get_pipeline

router = APIRouter()
logger = logging.getLogger("gateway_api")

# Single source of truth: provider-error kind → HTTP status (Epic 5, FR-023).
# unknown_model is raised by the router before any adapter call (FR-015); auth is a
# missing/invalid API key (FR-021); rate_limit is an upstream 429 with no retry
# (FR-020). Existing Epic 4 kinds (unreachable/missing_model → 503, timeout → 504)
# are unchanged.
_ERROR_STATUS: dict[ProviderErrorKind, int] = {
    "unreachable": 503,
    "missing_model": 503,
    "timeout": 504,
    "rate_limit": 429,
    "auth": 503,
    "unknown_model": 400,
}


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None
    model: str | None = None


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    session_id: str
    choices: list[Choice]


def _error(status_code: int, message: str, session_id: str) -> JSONResponse:
    """Error body that always preserves the session_id (FR-021/FR-022)."""
    return JSONResponse(
        status_code=status_code, content={"detail": message, "session_id": session_id}
    )


@router.post("/v1/chat/completions")
async def chat_completions(
        request: ChatCompletionRequest,
        provider: LLMProvider = Depends(get_llm_provider),  # noqa: B008 — FastAPI DI
):
    session_id = request.session_id or uuid.uuid4().hex

    # --- request validation (before any LLM call) — FR-021 -------------------
    if not request.messages:
        return _error(400, "messages must not be empty", session_id)

    if request.messages[-1].role != "user":
        return _error(400, "the last message must be a user turn", session_id)

    if not nlp.is_model_ready():
        return _error(503, "Detection model not ready", session_id)

    pipeline = get_pipeline()

    if pipeline is None:  # Redis unavailable (the gate normally catches this first)
        return _error(503, "Redis unavailable", session_id)

    model = request.model or get_settings().default_model

    # --- inbound: pseudonymize the WHOLE history (FR-005) --------------------
    fake_messages = await pipeline.pseudonymize_messages(session_id, request.messages)

    # --- LLM round-trip (synchronous; full answer before restore — FR-025) ---
    try:
        fake_answer = await provider.complete(fake_messages, model=model)
    except LLMProviderError as llmException:
        status_code = _ERROR_STATUS.get(llmException.kind, 503)
        logger.info(
            "chat session=%s provider_error=%s status=%d",
            session_id,
            llmException.kind,
            status_code,
        )
        return _error(status_code, str(llmException), session_id)

    # --- outbound: restore originals in the answer for display (FR-007) ------
    answer = await pipeline.depseudonymize_text(session_id, fake_answer)

    logger.info(
        "chat session=%s messages=%d model=%s status=200",
        session_id,
        len(request.messages),
        model,
    )

    return ChatCompletionResponse(
        session_id=session_id,
        choices=[
            Choice(
                index=0,
                message=ChatMessage(role="assistant", content=answer),
                finish_reason=None,
            )
        ],
    )
