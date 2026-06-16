"""NIP recognizer tests (T022, FR-009)."""

from __future__ import annotations

from gateway_api.pii_detection.recognizers.nip import NipRecognizer
from gateway_api.pii_detection.scoring import S_INVALID, S_VALID

REC = NipRecognizer()


def _detect(text):
    return REC.analyze(text, ["NIP"], nlp_artifacts=None)


def test_valid_nip_plain():
    r = _detect("NIP 1234563218")[0]
    assert r.score == S_VALID
    assert r.recognition_metadata["pii"]["checksum_valid"] is True


def test_valid_nip_dashed_normalizes_keeps_original_span():
    text = "NIP 123-456-32-18 koniec"
    r = _detect(text)[0]
    assert text[r.start : r.end] == "123-456-32-18"
    assert r.recognition_metadata["pii"]["normalized"] == "1234563218"
    assert r.score == S_VALID


def test_leading_zero_nip_is_valid():
    r = _detect("NIP 0123456789")[0]
    assert r.score == S_VALID
    assert r.recognition_metadata["pii"]["checksum_valid"] is True


def test_bad_checksum_nip_surfaced_low():
    r = _detect("NIP 1234567890")[0]
    assert r.score == S_INVALID
    assert r.recognition_metadata["pii"]["checksum_valid"] is False
