"""Polish bank account recognizer tests (T024, FR-011)."""

from __future__ import annotations

from gateway_api.pii_detection.recognizers.bank_account import (
    PolishBankAccountRecognizer,
)
from gateway_api.pii_detection.scoring import S_INVALID, S_VALID

REC = PolishBankAccountRecognizer()


def _detect(text):
    return REC.analyze(text, ["POLISH_BANK_ACCOUNT"], nlp_artifacts=None)


def _longest(results):
    return max(results, key=lambda r: r.end - r.start)


def test_iban_pl_prefixed_spaced():
    text = "nr rachunku PL61 1090 1014 0000 0712 1981 2874"
    r = _longest(_detect(text))
    assert text[r.start : r.end].startswith("PL61")  # original span preserved
    meta = r.recognition_metadata["pii"]
    assert meta["format"] == "IBAN"
    assert meta["mod97_valid"] is True
    assert meta["normalized"] == "61109010140000071219812874"
    assert r.score == S_VALID


def test_continuous_nrb():
    r = _longest(_detect("konto 61109010140000071219812874"))
    meta = r.recognition_metadata["pii"]
    assert meta["format"] == "NRB"
    assert meta["mod97_valid"] is True
    assert r.score == S_VALID


def test_bad_mod97_still_surfaced_low():
    r = _longest(_detect("konto 61109010140000071219812875"))
    assert r.score == S_INVALID
    assert r.recognition_metadata["pii"]["mod97_valid"] is False
