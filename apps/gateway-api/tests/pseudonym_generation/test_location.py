"""City + atomic address builders (T015, FR-001/FR-019)."""

from __future__ import annotations

import re

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator


def _gen(entity_type, seed=1):
    e = DetectedEntity(entity_type=entity_type, start=0, end=1, score=1.0, text="x")
    return FakeDataGenerator(seed=seed).generate(e)


def test_city_has_inflection_forms():
    v = _gen("LOCATION")
    assert v.base
    assert v.forms and "loc" in v.forms


def test_address_is_atomic():
    v = _gen("POLISH_ADDRESS")
    assert v.forms is None  # never internally inflected
    assert v.base.startswith("ul. ")
    assert re.search(r"\d{2}-\d{3}", v.base)  # postal code
