"""Recognizer registry assembly test (T016/T033, FR-004).

Constructs the registry without loading the model (SpacyRecognizer construction
does not load spaCy) — guards the recognizer wiring and entity coverage.
"""

from __future__ import annotations

from gateway_api.pii_detection.recognizers import ALL_ENTITIES, build_registry


def test_registry_contains_all_recognizers():
    registry = build_registry()
    names = {r.name for r in registry.recognizers}
    for expected in (
        "SpacyRecognizer",
        "EmailRecognizer",
        "PhoneRecognizer",
        "DateRecognizer",
        "PeselRecognizer",
        "NipRecognizer",
        "RegonRecognizer",
        "PolishBankAccountRecognizer",
        "PolishAddressRecognizer",
    ):
        assert expected in names


def test_all_entities_covered_by_some_recognizer():
    registry = build_registry()
    supported: set[str] = set()
    for rec in registry.recognizers:
        supported.update(rec.supported_entities)
    for entity in ALL_ENTITIES:
        assert entity in supported, f"{entity} has no recognizer"
