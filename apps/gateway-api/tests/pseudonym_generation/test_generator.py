"""Generator dispatch + seed determinism (T017)."""

from __future__ import annotations

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator

_TYPES = [
    "PERSON",
    "LOCATION",
    "POLISH_ADDRESS",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "DATE_TIME",
    "PESEL",
    "NIP",
    "REGON",
    "POLISH_BANK_ACCOUNT",
]


def _e(entity_type, text="x"):
    return DetectedEntity(
        entity_type=entity_type,
        start=0,
        end=len(text),
        score=1.0,
        text=text,
        metadata={"gender": "male", "variant": "9"},
    )


def test_dispatch_all_types_produce_a_value():
    g = FakeDataGenerator(seed=1)
    for t in _TYPES:
        v = g.generate(_e(t))
        assert v.entity_type == t
        assert v.base


def test_unknown_type_echoes_original():
    v = FakeDataGenerator(seed=1).generate(_e("ORGANIZATION", text="ACME"))
    assert v.base == "ACME"


def test_seed_reproducibility():
    e = _e("PERSON")
    assert (
        FakeDataGenerator(seed=9).generate(e).base
        == FakeDataGenerator(seed=9).generate(e).base
    )
