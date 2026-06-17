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
from .nlp import get_doc, get_nlp_engine
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
        key=lambda entity: (
            -(entity.end - entity.start),
            entity.start,
            -entity.score,
            entity.entity_type,
        ),
    )
    kept: list[DetectedEntity] = []
    for entity in ordered:
        if any(_subsumed_by(entity, kept_entity) for kept_entity in kept):
            continue
        kept.append(entity)
    return kept


def _subsumed_by(entity: DetectedEntity, kept_entity: DetectedEntity) -> bool:
    contained = kept_entity.start <= entity.start and entity.end <= kept_entity.end
    if not contained:
        return False
    # kept_entity is strictly longer → it wins (containing span subsumes the
    # shorter one), or identical span → entity duplicates the kept higher-score one.
    return (kept_entity.end - kept_entity.start) >= (entity.end - entity.start)


_NAME_TYPES = frozenset({"PERSON", "LOCATION"})


def _enrich_morphology(entities: list[DetectedEntity], text: str) -> None:
    """Fill ``lemma`` + ``case`` for kept PERSON/LOCATION entities (research D1).

    Maps each name span back to spaCy tokens (lemma + ``token.morph`` Case). Other
    types are left untouched. Failure (no model / no span) leaves the fields None —
    substitution then falls back to the base form (documented limitation).
    """
    targets = [entity for entity in entities if entity.entity_type in _NAME_TYPES]
    if not targets:
        return
    try:
        doc = get_doc(text)
    except Exception:  # noqa: BLE001 — model unavailable → leave lemma/case None (D8)
        return
    if doc is None:
        return
    for entity in targets:
        span = doc.char_span(entity.start, entity.end, alignment_mode="expand")
        if span is None or len(span) == 0:
            continue
        entity.lemma = " ".join(token.lemma_ for token in span).strip() or None
        case_values = span.root.morph.get("Case")
        entity.case = case_values[0].lower() if case_values else None


class DetectionEngine:
    """Wraps the Presidio analyzer; the only detection entry point (FR-006)."""

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text or not text.strip():
            return []
        start = time.perf_counter()
        raw = _get_analyzer().analyze(
            text=text, language="pl", entities=list(ALL_ENTITIES)
        )
        entities = [_result_to_dto(result, text) for result in raw]
        entities = resolve_overlaps(entities)
        entities = apply_thresholds(entities)
        _enrich_morphology(entities, text)
        entities.sort(key=lambda entity: (entity.start, entity.end))
        duration_ms = (time.perf_counter() - start) * 1000
        # No PII: only types/counts/scores/timing (Constitution VIII).
        logger.info(
            "detect chars=%d entities=%d types=%s duration_ms=%.1f",
            len(text),
            len(entities),
            sorted({entity.entity_type for entity in entities}),
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
