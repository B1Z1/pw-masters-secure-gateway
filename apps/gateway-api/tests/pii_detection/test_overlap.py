"""Overlap-resolution tests (T039, FR-023/FR-024/FR-025/FR-026, SC-008, research D4)."""

from __future__ import annotations

from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pii_detection.engine import resolve_overlaps


def _e(entity_type, start, end, score=0.8):
    return DetectedEntity(
        entity_type=entity_type,
        start=start,
        end=end,
        score=score,
        text="x" * (end - start),
    )


def test_nip_inside_pesel_keeps_pesel():
    out = resolve_overlaps([_e("PESEL", 0, 11), _e("NIP", 0, 10)])
    assert len(out) == 1
    assert out[0].entity_type == "PESEL"


def test_regon9_inside_regon14_keeps_14():
    out = resolve_overlaps([_e("REGON", 0, 14), _e("REGON", 0, 9)])
    assert len(out) == 1
    assert out[0].end == 14


def test_address_subsumes_contained_location_even_if_higher_score():
    address = _e("POLISH_ADDRESS", 0, 30, score=0.6)
    city = _e("LOCATION", 20, 28, score=0.99)  # higher score but contained
    out = resolve_overlaps([address, city])
    assert len(out) == 1
    assert out[0].entity_type == "POLISH_ADDRESS"


def test_adjacent_person_spans_both_kept():
    out = resolve_overlaps([_e("PERSON", 0, 3), _e("PERSON", 4, 9)])
    assert len(out) == 2


def test_identical_span_duplicates_collapse_to_one():
    out = resolve_overlaps([_e("DATE_TIME", 0, 10, 0.6), _e("DATE_TIME", 0, 10, 0.55)])
    assert len(out) == 1
    assert out[0].score == 0.6  # higher score kept
