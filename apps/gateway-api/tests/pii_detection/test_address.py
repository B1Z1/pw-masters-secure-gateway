"""Polish address recognizer tests (T025, FR-012)."""

from __future__ import annotations

from gateway_api.pii_detection.recognizers.address import PolishAddressRecognizer
from gateway_api.pii_detection.scoring import S_ADDRESS_NO_STREET, S_ADDRESS_WITH_STREET

REC = PolishAddressRecognizer()


def _detect(text):
    return REC.analyze(text, ["POLISH_ADDRESS"], nlp_artifacts=None)


def _longest(results):
    return max(results, key=lambda r: r.end - r.start)


def test_full_address_with_street():
    text = "Adres: ul. Kowalskiego 12/3, 00-950 Warszawa"
    r = _longest(_detect(text))
    meta = r.recognition_metadata["pii"]
    assert meta["has_street"] is True
    assert meta["postal_code"] == "00-950"
    assert r.score == S_ADDRESS_WITH_STREET


def test_address_without_street_lower_confidence():
    results = _detect("00-950 Warszawa")
    r = _longest(results)
    assert r.recognition_metadata["pii"]["has_street"] is False
    assert r.score == S_ADDRESS_NO_STREET


def test_multiline_address():
    text = "ul. Polna 5\n00-001 Miasto"
    r = _longest(_detect(text))
    assert r.recognition_metadata["pii"]["has_street"] is True
    assert r.recognition_metadata["pii"]["postal_code"] == "00-001"


def test_street_surname_kept_in_address_span():
    # "ul. Kowalskiego 7" — the surname-as-street is part of the address span.
    text = "ul. Kowalskiego 7"
    r = _longest(_detect(text))
    assert r.recognition_metadata["pii"]["has_street"] is True
    assert "Kowalskiego" in text[r.start : r.end]
