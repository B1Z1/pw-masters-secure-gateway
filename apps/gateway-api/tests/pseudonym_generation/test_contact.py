"""Email + phone builders (T014, FR-005)."""

from __future__ import annotations

import re

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator


def _gen(entity_type, seed=1):
    e = DetectedEntity(entity_type=entity_type, start=0, end=1, score=1.0, text="x")
    return FakeDataGenerator(seed=seed).generate(e)


def test_phone_polish_format():
    for seed in range(10):
        base = _gen("PHONE_NUMBER", seed=seed).base
        assert re.fullmatch(r"\+48 \d{3} \d{3} \d{3}", base)
        assert base[4] in "5678"  # plausible mobile leading digit


def test_email_shape():
    base = _gen("EMAIL_ADDRESS").base
    local, _, domain = base.partition("@")
    assert local and "." in domain
