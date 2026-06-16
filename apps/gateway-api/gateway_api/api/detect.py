"""``POST /v1/detect`` — the detection debug endpoint (FR-027, FR-030).

Thin layer over ``DetectionEngine``: no substitution, no storage, no LLM. Returns
HTTP 503 while the language model is not ready (it does NOT return partial
results — spec clarification 2026-06-16). Exempt from the Epic 1 Redis gate (the
exemption lives in main.py — FR-031).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..detection import engine as _engine
from ..detection import nlp as _nlp
from ..detection.dto import DetectedEntity

router = APIRouter()


class DetectRequest(BaseModel):
    text: str


class DetectResponse(BaseModel):
    entities: list[DetectedEntity]


@router.post("/v1/detect", response_model=DetectResponse)
async def detect(request: DetectRequest) -> DetectResponse:
    if not _nlp.is_model_ready():
        raise HTTPException(status_code=503, detail="Detection model not ready")

    entities = _engine.get_engine().detect(request.text)

    return DetectResponse(entities=entities)
