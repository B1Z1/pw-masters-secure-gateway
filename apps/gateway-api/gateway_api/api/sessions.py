"""Epic 6 session management — GET/DELETE /v1/sessions/{session_id} (FR-018..FR-021).

``GET`` returns the dashboard statistics (created/last-activity, live TTL, the
distinct-mapping counts grouped by entity type, and the successful round-trip
count); ``DELETE`` resets the session (removes the hash and ALL its mappings).
Both return 404 when the session has no stored state — non-existent, TTL-expired,
or a session in which no PII was ever detected ("nothing to manage"). NOT
gate-exempt: they need Redis. No auth — anyone holding a ``session_id`` may read or
delete it (documented prototype limitation, FR-026). Logs carry session_id +
counts only (Constitution VIII). Coexists with the Epic 3 debug
``GET /v1/sessions/{id}/mappings``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..pseudonym_vault.mapping_store import get_mapping_store

router = APIRouter()
logger = logging.getLogger("gateway_api")


class SessionSummaryResponse(BaseModel):
    session_id: str
    created_at: str
    last_activity: str
    ttl_remaining_seconds: int
    entity_count: int
    entities_by_type: dict[str, int]
    message_count: int


def _store_or_503():
    store = get_mapping_store()

    if store is None:  # Redis unavailable (the gate normally catches this first)
        raise HTTPException(status_code=503, detail="Redis unavailable")

    return store


@router.get("/v1/sessions/{session_id}", response_model=SessionSummaryResponse)
async def get_session(session_id: str) -> SessionSummaryResponse:
    summary = await _store_or_503().get_session_summary(session_id)

    if summary is None:  # no stored state → unmanageable (FR-021)
        raise HTTPException(status_code=404, detail="session not found")

    logger.info(
        "get_session session=%s entities=%d messages=%d",
        session_id,
        summary["entity_count"],
        summary["message_count"],
    )

    return SessionSummaryResponse(**summary)


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    existed = await _store_or_503().delete_session(session_id)

    if not existed:  # non-existent / TTL-expired / never stored (FR-020/FR-021)
        raise HTTPException(status_code=404, detail="session not found")

    logger.info("delete_session session=%s deleted=true", session_id)

    return {"session_id": session_id, "deleted": True}
