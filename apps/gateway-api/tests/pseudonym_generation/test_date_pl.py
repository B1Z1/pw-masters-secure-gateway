"""DATE_TIME builder: ±10-year window, DD.MM.YYYY (T016, FR-006, research D9)."""

from __future__ import annotations

import re

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator


def _date(text, seed=1):
    e = DetectedEntity(
        entity_type="DATE_TIME", start=0, end=len(text), score=1.0, text=text
    )
    return FakeDataGenerator(seed=seed).generate(e).base


def test_format_and_window():
    for seed in range(15):
        base = _date("12.01.2024", seed=seed)
        assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", base)
        year = int(base[-4:])
        assert 2014 <= year <= 2034  # within ±10 years of 2024


def test_no_year_in_source_still_plausible():
    base = _date("kiedyś w styczniu")
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", base)
