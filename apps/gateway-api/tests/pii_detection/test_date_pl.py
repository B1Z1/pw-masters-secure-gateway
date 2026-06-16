"""Polish date recognizer tests (T013, FR-004 DATE_TIME)."""

from __future__ import annotations

from gateway_api.pii_detection.recognizers.date_pl import DateRecognizer
from gateway_api.pii_detection.scoring import S_DATE_NUMERIC, S_DATE_WORDED

REC = DateRecognizer()


def _detect(text):
    return REC.analyze(text, ["DATE_TIME"], nlp_artifacts=None)


def test_numeric_dot():
    text = "data 12.01.2024 r"
    r = next(
        x for x in _detect(text) if x.recognition_metadata["pii"]["kind"] == "numeric"
    )
    assert text[r.start : r.end] == "12.01.2024"
    assert r.score == S_DATE_NUMERIC


def test_numeric_dash():
    r = _detect("12-01-2024")[0]
    assert r.recognition_metadata["pii"]["kind"] == "numeric"


def test_worded_with_r_marker():
    text = "dnia 12 stycznia 2024 r."
    r = next(
        x for x in _detect(text) if x.recognition_metadata["pii"]["kind"] == "worded"
    )
    assert "stycznia" in text[r.start : r.end]
    assert r.score == S_DATE_WORDED


def test_worded_without_marker():
    r = _detect("5 marca 2020")[0]
    assert r.recognition_metadata["pii"]["kind"] == "worded"
