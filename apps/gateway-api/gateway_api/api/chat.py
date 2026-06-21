"""Epic 6 chat endpoint — the full, frontend-ready chat-completions contract.

``POST /v1/chat/completions`` keeps the Epic 4/5 flow (pseudonymize the WHOLE
history → call exactly one provider via the router → de-pseudonymize the answer)
but returns the COMPLETE OpenAI-shaped response plus the gateway extensions the
React SPA needs: a real, normalized ``finish_reason``; ``anonymization_meta``
(per-type counts over the whole history, totals, provider, model, timing); and
``input_anonymization`` (the latest user message's synthetic text + replacements
with offsets into the original). Per-stage timing + per-type counts are stashed on
``request.state`` for the logging middleware. NOT gate-exempt — it needs Redis.

Validation runs before any provider call (400, preserving ``session_id``).
Provider failures map to 503/504/429 via the centralized ``_ERROR_STATUS`` map and
also preserve ``session_id``. Logs/response carry no original content (Constitution
VIII): originals appear only in ``input_anonymization`` (the trusted client hop).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import get_settings
from ..llm_providers import LLMProvider, LLMProviderError, get_llm_provider
from ..llm_providers.base import ChatMessage, ProviderErrorKind
from ..observability.request_metrics import RequestMetrics
from ..pii_detection import nlp
from ..pipeline.anonymization_pipeline import Replacement, get_pipeline

router = APIRouter()
logger = logging.getLogger("gateway_api")

# Single source of truth: provider-error kind → HTTP status (Epic 5, FR-023).
_ERROR_STATUS: dict[ProviderErrorKind, int] = {
    "unreachable": 503,
    "missing_model": 503,
    "timeout": 504,
    "rate_limit": 429,
    "auth": 503,
    "unknown_model": 400,
}


_VALID_ROLES = frozenset({"system", "user", "assistant"})


class ChatInputMessage(BaseModel):
    """Permissive inbound message (FR-007/D6): bad role/content is a handler 400
    (preserving session_id), never a pre-handler 422 that would drop it."""

    role: str | None = None
    content: Any = None


class ChatCompletionRequest(BaseModel):
    messages: list[ChatInputMessage]
    session_id: str | None = None
    model: str | None = None


class ChatMessageOut(BaseModel):
    role: str
    content: str


class Choice(BaseModel):
    index: int
    message: ChatMessageOut
    finish_reason: str  # real, normalized to OpenAI vocab ("stop"/"length")


class TimingBreakdown(BaseModel):
    ner_analysis: float
    fake_generation: float
    redis_write: float
    llm_request: float
    deanonymization: float
    total: float


class AnonymizationMeta(BaseModel):
    entities_detected: dict[str, int]
    total_entities: int
    provider: str
    model: str
    processing_time_ms: float
    timing_ms: TimingBreakdown


class InputAnonymization(BaseModel):
    pseudonymized_content: str
    replacements: list[Replacement]


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]
    session_id: str
    anonymization_meta: AnonymizationMeta
    input_anonymization: InputAnonymization


def _error(status_code: int, message: str, session_id: str) -> JSONResponse:
    """Error body that always preserves the session_id (FR-010)."""
    return JSONResponse(
        status_code=status_code, content={"detail": message, "session_id": session_id}
    )


def _metrics(http_request: Request) -> RequestMetrics:
    """The request-scoped metrics — get-or-create so the endpoint works whether or
    not the logging middleware is installed (D11)."""
    metrics = getattr(http_request.state, "gateway_metrics", None)

    if metrics is None:
        metrics = RequestMetrics()
        http_request.state.gateway_metrics = metrics

    return metrics


@router.post("/v1/chat/completions")
async def chat_completions(
        request: ChatCompletionRequest,
        http_request: Request,
        provider: LLMProvider = Depends(get_llm_provider),  # noqa: B008 — FastAPI DI
):
    request_start = time.perf_counter()
    metrics = _metrics(http_request)
    session_id = request.session_id or uuid.uuid4().hex
    metrics.session_id = session_id

    # --- request validation (before any LLM call) — FR-007 -------------------
    if not request.messages:
        return _error(400, "messages must not be empty", session_id)

    for message in request.messages:
        if message.role not in _VALID_ROLES:
            return _error(400, f"invalid message role: {message.role!r}", session_id)
        if not isinstance(message.content, str):
            return _error(400, "message content must be a string", session_id)

    if request.messages[-1].role != "user":
        return _error(400, "the last message must be a user turn", session_id)

    if not nlp.is_model_ready():
        return _error(503, "Detection model not ready", session_id)

    pipeline = get_pipeline()

    if pipeline is None:  # Redis unavailable (the gate normally catches this first)
        return _error(503, "Redis unavailable", session_id)

    model = request.model or get_settings().default_model
    metrics.model = model

    # Validated → convert to the provider port's ChatMessage (content is now a str).
    chat_messages = [
        ChatMessage(role=message.role, content=message.content)
        for message in request.messages
    ]

    # --- inbound: pseudonymize the WHOLE history (FR-005/FR-006) -------------
    inbound = await pipeline.run_inbound(session_id, chat_messages)
    metrics.is_chat = True
    metrics.entities_detected = inbound.entities_detected
    metrics.ner_analysis_ms = inbound.timing.ner_analysis_ms
    metrics.fake_generation_ms = inbound.timing.fake_generation_ms
    metrics.redis_write_ms = inbound.timing.redis_write_ms

    # --- LLM round-trip (synchronous; full answer before restore — FR-025) ---
    try:
        llm_start = time.perf_counter()
        result = await provider.complete(inbound.fake_messages, model=model)
        metrics.llm_request_ms = (time.perf_counter() - llm_start) * 1000
    except LLMProviderError as llmException:
        status_code = _ERROR_STATUS.get(llmException.kind, 503)
        metrics.total_ms = (time.perf_counter() - request_start) * 1000
        logger.info(
            "chat session=%s provider_error=%s status=%d",
            session_id,
            llmException.kind,
            status_code,
        )
        return _error(status_code, str(llmException), session_id)

    metrics.provider = result.provider

    # --- outbound: restore originals in the answer for display (FR-003) ------
    deanon_start = time.perf_counter()
    answer = await pipeline.depseudonymize_text(session_id, result.content)
    metrics.deanonymization_ms = (time.perf_counter() - deanon_start) * 1000

    # A successful round-trip counts toward the session (no-op if no PII state).
    await pipeline.increment_message_count(session_id)

    metrics.total_ms = (time.perf_counter() - request_start) * 1000
    timing = metrics.timing_ms()  # the SAME object the log line emits (FR-005)

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        object="chat.completion",
        created=int(time.time()),
        model=model,
        choices=[
            Choice(
                index=0,
                message=ChatMessageOut(role="assistant", content=answer),
                finish_reason=result.finish_reason,
            )
        ],
        session_id=session_id,
        anonymization_meta=AnonymizationMeta(
            entities_detected=inbound.entities_detected,
            total_entities=inbound.total_entities,
            provider=result.provider,
            model=model,
            processing_time_ms=timing["total"],
            timing_ms=TimingBreakdown(**timing),
        ),
        input_anonymization=InputAnonymization(
            pseudonymized_content=inbound.last_user_pseudonymized,
            replacements=inbound.last_user_replacements,
        ),
    )
