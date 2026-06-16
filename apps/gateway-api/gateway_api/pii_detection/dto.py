"""Detection output DTO (data-model §1, research D7).

The single unit returned by ``DetectionEngine.detect()`` and serialized by
``POST /v1/detect``. A project model — NOT raw Presidio ``RecognizerResult`` —
so the rest of the system is decoupled from Presidio internals and so we have a
``metadata`` channel that ``RecognizerResult`` lacks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectedEntity(BaseModel):
    """A single detected PII entity (FR-002)."""

    entity_type: str
    start: int
    end: int
    score: float
    text: str
    metadata: dict = Field(default_factory=dict)
    # Epic 3 (data-model §1): base form + grammatical case from spaCy, filled for
    # PERSON/LOCATION only; None for every other type. Enables case-aware
    # substitution without coupling the rest of the system to spaCy.
    lemma: str | None = None
    case: str | None = None
