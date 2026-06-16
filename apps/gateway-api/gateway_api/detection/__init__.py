"""PII detection layer (Epic 2). Detection only — no substitution/storage/LLM."""

from __future__ import annotations

from .dto import DetectedEntity
from .engine import DetectionEngine, get_engine

__all__ = ["DetectedEntity", "DetectionEngine", "get_engine"]
