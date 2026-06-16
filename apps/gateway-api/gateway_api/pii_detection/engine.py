"""DetectionEngine — the single entry point for PII detection (research D1/D4/D7).

``detect(text)`` runs the Presidio ``AnalyzerEngine`` (spaCy ``pl_core_news_lg`` +
custom Polish recognizers), maps results to ``DetectedEntity`` DTOs, resolves
overlaps deterministically (longest/containing span wins; ADDRESS subsumes a
contained LOCATION), and applies the per-type threshold post-filter. Detection
only — no substitution, no storage, no LLM, no Redis. Logs carry only entity
types/counts/scores/timings, never the input text or matched values (Constitution VIII).
"""

from __future__ import annotations

import logging
import time
from threading import Lock

from .dto import DetectedEntity
from .nlp import get_nlp_engine
from .recognizers import ALL_ENTITIES, build_registry
from .scoring import (
    CONTEXT_MIN_SCORE,
    CONTEXT_SIMILARITY_FACTOR,
    clamp_score,
)
from .thresholds import apply_thresholds

logger = logging.getLogger("gateway_api")

_lock = Lock()
_analyzer = None


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer

    enhancer = LemmaContextAwareEnhancer(
        context_similarity_factor=CONTEXT_SIMILARITY_FACTOR,
        min_score_with_context_similarity=CONTEXT_MIN_SCORE,
    )
    return AnalyzerEngine(
        nlp_engine=get_nlp_engine(),
        registry=build_registry(),
        supported_languages=["pl"],
        context_aware_enhancer=enhancer,
    )


def _get_analyzer():
    """Lazily build the singleton AnalyzerEngine (loads the model on first call)."""
    global _analyzer
    if _analyzer is None:
        with _lock:
            if _analyzer is None:
                _analyzer = _build_analyzer()
    return _analyzer


def _result_to_dto(result, text: str) -> DetectedEntity:
    rm = getattr(result, "recognition_metadata", None)
    meta = {}
    if isinstance(rm, dict) and isinstance(rm.get("pii"), dict):
        meta = dict(rm["pii"])
    return DetectedEntity(
        entity_type=result.entity_type,
        start=result.start,
        end=result.end,
        score=clamp_score(float(result.score)),
        text=text[result.start : result.end],
        metadata=meta,
    )


def resolve_overlaps(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Keep one best entity per region (research D4, FR-023/FR-024/FR-025).

    Longest/containing span wins; a shorter span fully contained in a longer kept
    span is dropped (this also makes an ADDRESS subsume any contained LOCATION/
    city). Equal-span duplicates collapse to the higher score. Adjacent,
    non-overlapping spans (e.g. first + last name) are both kept (FR-026).
    """
    # Deterministic order: longest first, then earliest, then higher score, then type.
    ordered = sorted(
        entities,
        key=lambda e: (-(e.end - e.start), e.start, -e.score, e.entity_type),
    )
    kept: list[DetectedEntity] = []
    for e in ordered:
        if any(_subsumed_by(e, k) for k in kept):
            continue
        kept.append(e)
    return kept


def _subsumed_by(e: DetectedEntity, k: DetectedEntity) -> bool:
    contained = k.start <= e.start and e.end <= k.end
    if not contained:
        return False
    # k is strictly longer → it wins (containing span subsumes the shorter one),
    # or identical span → e is a duplicate of the already-kept (higher-score) k.
    return (k.end - k.start) >= (e.end - e.start)


class DetectionEngine:
    """Wraps the Presidio analyzer; the only detection entry point (FR-006)."""

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text or not text.strip():
            return []
        start = time.perf_counter()
        raw = _get_analyzer().analyze(
            text=text, language="pl", entities=list(ALL_ENTITIES)
        )
        entities = [_result_to_dto(r, text) for r in raw]
        entities = resolve_overlaps(entities)
        entities = apply_thresholds(entities)
        entities.sort(key=lambda e: (e.start, e.end))
        duration_ms = (time.perf_counter() - start) * 1000
        # No PII: only types/counts/scores/timing (Constitution VIII).
        logger.info(
            "detect chars=%d entities=%d types=%s duration_ms=%.1f",
            len(text),
            len(entities),
            sorted({e.entity_type for e in entities}),
            duration_ms,
        )
        return entities


_engine: DetectionEngine | None = None


def get_engine() -> DetectionEngine:
    """Process-wide DetectionEngine singleton."""
    global _engine
    if _engine is None:
        _engine = DetectionEngine()
    return _engine
