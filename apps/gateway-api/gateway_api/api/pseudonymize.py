"""Epic 3 debug surface — substitution round-trip, NO LLM (FR-021/FR-022/FR-011).

``/v1/pseudonymize`` detects PII (reuse Epic 2) and substitutes realistic,
session-consistent fakes (case-correct for PERSON/LOCATION). ``/v1/depseudonymize``
restores the originals. ``GET /v1/sessions/{id}/mappings`` lists a session for
review. All three REQUIRE Redis → gated by the Epic 1 middleware (not exempt).
Logs carry session_id + types/counts only (Constitution VIII).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..pii_detection import nlp as _nlp
from ..pii_detection.engine import get_engine
from ..pseudonym_vault.mapping_store import get_mapping_store

router = APIRouter()
logger = logging.getLogger("gateway_api")


class PseudonymizeRequest(BaseModel):
    text: str
    session_id: str | None = None


class Replacement(BaseModel):
    entity_type: str
    original: str
    fake: str
    start: int  # offset into the ORIGINAL text
    end: int


class PseudonymizeResponse(BaseModel):
    pseudonymized_text: str
    entities_replaced: list[Replacement]
    session_id: str


class DepseudonymizeRequest(BaseModel):
    text: str
    session_id: str


class DepseudonymizeResponse(BaseModel):
    restored_text: str
    session_id: str


class SessionMappingsResponse(BaseModel):
    session_id: str
    mappings: list[dict]


def _store_or_503():
    store = get_mapping_store()

    if store is None:  # Redis unavailable (the gate normally catches this first)
        raise HTTPException(status_code=503, detail="Redis unavailable")

    return store


@router.post("/v1/pseudonymize", response_model=PseudonymizeResponse)
async def pseudonymize(request: PseudonymizeRequest) -> PseudonymizeResponse:
    session_id = request.session_id or uuid.uuid4().hex

    if not request.text or not request.text.strip():
        return PseudonymizeResponse(
            pseudonymized_text=request.text, entities_replaced=[], session_id=session_id
        )

    if not _nlp.is_model_ready():
        raise HTTPException(status_code=503, detail="Detection model not ready")

    store = _store_or_503()

    entities = get_engine().detect(request.text)
    items = [
        (entity, await store.get_or_create(session_id, entity)) for entity in entities
    ]

    text = request.text

    for entity, fake_form in sorted(
            items, key=lambda pair: pair[0].start, reverse=True
    ):
        text = text[: entity.start] + fake_form + text[entity.end:]

    replacements = [
        Replacement(
            entity_type=entity.entity_type,
            original=entity.text,
            fake=fake_form,
            start=entity.start,
            end=entity.end,
        )
        for entity, fake_form in items
    ]

    logger.info(
        "pseudonymize session=%s entities=%d types=%s",
        session_id,
        len(items),
        sorted({entity.entity_type for entity, _ in items}),
    )

    return PseudonymizeResponse(
        pseudonymized_text=text, entities_replaced=replacements, session_id=session_id
    )


@router.post("/v1/depseudonymize", response_model=DepseudonymizeResponse)
async def depseudonymize(request: DepseudonymizeRequest) -> DepseudonymizeResponse:
    if not request.text or not request.text.strip():
        return DepseudonymizeResponse(
            restored_text=request.text, session_id=request.session_id
        )

    store = _store_or_503()
    restored = await store.restore_text(request.session_id, request.text)

    logger.info(
        "depseudonymize session=%s chars=%d", request.session_id, len(request.text)
    )

    return DepseudonymizeResponse(restored_text=restored, session_id=request.session_id)


@router.get(
    "/v1/sessions/{session_id}/mappings", response_model=SessionMappingsResponse
)
async def list_session_mappings(session_id: str) -> SessionMappingsResponse:
    store = _store_or_503()
    mappings = await store.get_all_mappings(session_id)

    logger.info("list_mappings session=%s count=%d", session_id, len(mappings))

    return SessionMappingsResponse(session_id=session_id, mappings=mappings)
