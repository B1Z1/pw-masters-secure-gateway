"""PERSON builder: gender consistency, declinable surname, determinism (T012)."""

from __future__ import annotations

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator
from gateway_api.pseudonym_generation.inflection import Pattern, classify

_E = DetectedEntity(entity_type="PERSON", start=0, end=1, score=1.0, text="x")


def _person(seed=1):
    return FakeDataGenerator(seed=seed).generate(_E)


def test_two_token_name_with_forms():
    p = _person()
    assert len(p.base.split()) == 2
    assert p.forms and {"nom", "gen"} <= set(p.forms)
    assert p.gender in ("male", "female")


def test_surname_is_declinable():
    for seed in range(12):
        p = _person(seed)
        surname = p.base.split()[-1]
        assert classify(surname, p.gender) is not Pattern.INDECLINABLE


def test_deterministic_with_seed():
    assert _person(5).base == _person(5).base
    assert _person(5).forms == _person(5).forms
