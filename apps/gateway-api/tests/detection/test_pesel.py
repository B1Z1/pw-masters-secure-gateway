"""PESEL recognizer tests (T021, FR-008/FR-014)."""

from __future__ import annotations

from gateway_api.detection.recognizers.pesel import PeselRecognizer
from gateway_api.detection.scoring import S_INVALID, S_VALID

REC = PeselRecognizer()


def _detect(text):
    return REC.analyze(text, ["PESEL"], nlp_artifacts=None)


def test_valid_pesel_detected_high_score_with_metadata():
    results = _detect("Numer PESEL 44051401359 w aktach")
    assert len(results) == 1
    r = results[0]
    assert r.score == S_VALID
    meta = r.recognition_metadata["pii"]
    assert meta["checksum_valid"] is True
    assert meta["gender"] == "male"
    assert meta["birth_date"] == "1944-05-14"
    assert meta["normalized"] == "44051401359"


def test_bad_checksum_pesel_still_surfaced_low_score():
    results = _detect("PESEL 44051401358")  # last digit wrong
    assert len(results) == 1
    assert results[0].score == S_INVALID  # kept, not dropped (FR-014)
    assert results[0].recognition_metadata["pii"]["checksum_valid"] is False


def test_offsets_reference_original_span():
    text = "x 44051401359 y"
    r = _detect(text)[0]
    assert text[r.start : r.end] == "44051401359"


def test_post_2000_pesel_birthdate():
    # Construct an 11-digit value with month-offset date; checksum may differ but
    # birth_date metadata must reflect the post-2000 century.
    results = _detect("02211012340")
    assert results[0].recognition_metadata["pii"]["birth_date"] == "2002-01-10"
