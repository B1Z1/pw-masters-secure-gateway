"""DetectionEngine pipeline tests (T014, FR-001/FR-002/FR-003, SC-002/SC-005/SC-010).

The pipeline (DTO mapping, overlap, threshold post-filter, sort) is exercised with
a fake analyzer so it runs without loading pl_core_news_lg. One integration test
runs the real analyzer and is skipped if the model is not installed.
"""

from __future__ import annotations

import pytest
from presidio_analyzer import RecognizerResult

from gateway_api.detection.engine import DetectionEngine

try:  # the Polish model is baked into the Docker image; optional for native dev
    import pl_core_news_lg  # noqa: F401

    HAS_MODEL = True
except Exception:  # noqa: BLE001
    HAS_MODEL = False


def _rr(entity_type, start, end, score, pii=None):
    r = RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)
    if pii is not None:
        r.recognition_metadata = {"pii": pii}
    return r


def test_empty_input_returns_empty_list():
    assert DetectionEngine().detect("") == []
    assert DetectionEngine().detect("   \n ") == []


def test_offsets_and_text_match_original(patch_analyzer):
    text = "Jan 44051401359 xx"
    patch_analyzer([_rr("PESEL", 4, 15, 0.99, {"gender": "male"})])
    out = DetectionEngine().detect(text)
    assert len(out) == 1
    e = out[0]
    assert e.text == text[e.start : e.end] == "44051401359"
    assert e.metadata["gender"] == "male"
    assert e.score <= 0.99


def test_overlap_resolved_in_pipeline(patch_analyzer):
    text = "01234567890 rest"
    patch_analyzer([_rr("PESEL", 0, 11, 0.9), _rr("NIP", 0, 10, 0.9)])
    out = DetectionEngine().detect(text)
    assert [e.entity_type for e in out] == ["PESEL"]


def test_threshold_filter_drops_low_score(patch_analyzer):
    text = "Ala ma kota i psa"
    patch_analyzer([_rr("PERSON", 0, 3, 0.20), _rr("PERSON", 7, 11, 0.50)])
    out = DetectionEngine().detect(text)
    # PERSON default threshold 0.40: 0.20 dropped, 0.50 kept.
    assert len(out) == 1
    assert out[0].start == 7


def test_results_sorted_by_offset(patch_analyzer):
    text = "x" * 30
    patch_analyzer([_rr("PERSON", 10, 13, 0.9), _rr("PERSON", 0, 3, 0.9)])
    out = DetectionEngine().detect(text)
    assert [e.start for e in out] == [0, 10]


def test_determinism(patch_analyzer):
    text = "Jan 44051401359 xx"
    results = [_rr("PESEL", 4, 15, 0.99, {"gender": "male"})]
    patch_analyzer(results)
    first = DetectionEngine().detect(text)
    patch_analyzer(results)
    second = DetectionEngine().detect(text)
    assert [e.model_dump() for e in first] == [e.model_dump() for e in second]


@pytest.mark.skipif(
    not HAS_MODEL, reason="pl_core_news_lg not installed (baked into image)"
)
def test_real_detection_person_and_location():
    out = DetectionEngine().detect("Jan Kowalski mieszka w Warszawie.")
    types = {e.entity_type for e in out}
    assert "PERSON" in types
    assert "LOCATION" in types
    for e in out:
        assert e.score <= 0.99


@pytest.mark.skipif(
    not HAS_MODEL, reason="pl_core_news_lg not installed (baked into image)"
)
def test_real_context_scoring_labelled_higher_than_unlabelled():
    labelled = DetectionEngine().detect("PESEL: 44051401359")
    unlabelled = DetectionEngine().detect("44051401359 bez etykiety")
    lp = next(e for e in labelled if e.entity_type == "PESEL")
    up = next(e for e in unlabelled if e.entity_type == "PESEL")
    assert lp.score == 0.99  # valid + context label -> ceiling (FR-017)
    assert up.score < lp.score  # unlabelled still detected, lower (FR-018)
    assert lp.metadata["gender"] == "male"


@pytest.mark.skipif(
    not HAS_MODEL, reason="pl_core_news_lg not installed (baked into image)"
)
def test_real_address_subsumes_city_and_surname_street():
    out = DetectionEngine().detect("Adres: ul. Kowalskiego 12/3, 00-950 Warszawa")
    types = [e.entity_type for e in out]
    assert "POLISH_ADDRESS" in types
    assert "LOCATION" not in types  # city subsumed by the address (FR-024)
    assert "PERSON" not in types  # surname street is part of the address (FR-025)
