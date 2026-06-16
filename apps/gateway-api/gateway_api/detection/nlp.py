"""spaCy NLP engine + model readiness (research D1/D2/D8).

A process-singleton Presidio ``NlpEngine`` backed by spaCy ``pl_core_news_lg``,
configured with the **NKJP → Presidio label mapping** so the Polish model's
``persName``/``placeName``/``geogName``/``date`` labels surface as
PERSON/LOCATION/DATE_TIME (without this, base NER detects nothing — D2).

The engine loads **lazily on first use** so US1 is demoable before US5 wires the
eager startup load. ``is_model_ready()`` is an O(1) flag read consumed by
``/health`` and the ``/v1/detect`` readiness gate.
"""

from __future__ import annotations

import logging
from threading import Lock

logger = logging.getLogger("gateway_api")

SPACY_MODEL = "pl_core_news_lg"
LANGUAGE = "pl"

# pl_core_news_lg (NKJP) labels → Presidio entity types (research D2).
LABEL_MAPPING = {
    "persName": "PERSON",
    "placeName": "LOCATION",
    "geogName": "LOCATION",
    "orgName": "ORGANIZATION",
    "date": "DATE_TIME",
    "time": "DATE_TIME",
}

_lock = Lock()
_nlp_engine = None
_ready = False
_load_failed = False


def _build_nlp_engine():
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": LANGUAGE, "model_name": SPACY_MODEL}],
        "ner_model_configuration": {
            "model_to_presidio_entity_mapping": LABEL_MAPPING,
        },
    }
    return NlpEngineProvider(nlp_configuration=configuration).create_engine()


def get_nlp_engine():
    """Return the singleton NlpEngine, loading the model on first call (lazy)."""
    global _nlp_engine, _ready
    if _nlp_engine is not None:
        return _nlp_engine
    with _lock:
        if _nlp_engine is None:
            logger.info("loading spaCy model %s", SPACY_MODEL)
            _nlp_engine = _build_nlp_engine()
            _ready = True
            logger.info("spaCy model %s ready", SPACY_MODEL)
    return _nlp_engine


def ensure_loaded() -> bool:
    """Eager-load entry point (startup). Returns success; never raises (D8)."""
    global _load_failed
    try:
        get_nlp_engine()
        return True
    except Exception:  # noqa: BLE001 — a load failure degrades health, no crash
        _load_failed = True
        logger.warning(
            "spaCy model %s failed to load; detection unavailable", SPACY_MODEL
        )
        return False


def is_model_ready() -> bool:
    """O(1) readiness flag (FR-028/FR-030)."""
    return _ready
