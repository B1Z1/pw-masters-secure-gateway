"""REGON recognizer tests (T023, FR-010)."""

from __future__ import annotations

from gateway_api.detection.recognizers.regon import RegonRecognizer
from gateway_api.detection.scoring import S_INVALID, S_VALID

REC = RegonRecognizer()


def _detect(text):
    return REC.analyze(text, ["REGON"], nlp_artifacts=None)


def test_valid_regon9_variant_metadata():
    r = _detect("REGON 123456785")[0]
    assert r.score == S_VALID
    assert r.recognition_metadata["pii"]["variant"] == "9"
    assert r.recognition_metadata["pii"]["checksum_valid"] is True


def test_valid_regon14_variant_metadata():
    r = _detect("REGON 12345678500002")[0]
    assert r.score == S_VALID
    assert r.recognition_metadata["pii"]["variant"] == "14"


def test_bad_checksum_regon_surfaced_low():
    r = _detect("REGON 123456789")[0]
    assert r.score == S_INVALID
    assert r.recognition_metadata["pii"]["checksum_valid"] is False
