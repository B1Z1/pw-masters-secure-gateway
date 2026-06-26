"""T027 — leak audit: inflected/diacritic/structured leaks; no false leaks (D4)."""

from __future__ import annotations

from gateway_eval.corpus.gold_standard import GoldDocument
from gateway_eval.scoring.leak_audit import audit_document


def _doc(entities):
    # The audit reads the OUTBOUND text, not the gold text, so build a trivially valid
    # gold doc whose entity offsets match its own text.
    rebuilt = ""
    rebuilt_entities = []
    for type_, value in entities:
        rebuilt += "X "
        start = len(rebuilt)
        rebuilt += value
        rebuilt_entities.append({"type": type_, "start": start, "end": len(rebuilt), "text": value})
    return GoldDocument.model_validate(
        {"doc_id": "d1", "source": "synthetic", "contract_type": "najem",
         "text": rebuilt, "entities": rebuilt_entities}
    )


def test_inflected_surname_is_full_leak():
    document = _doc([("PERSON", "Kowalski")])
    findings = audit_document(document, "Pozdrawiam pana Kowalskiego serdecznie.")
    assert len(findings) == 1
    assert findings[0].type == "PERSON"
    assert findings[0].form_found == "Kowalskiego"


def test_exact_surname_is_leak():
    document = _doc([("PERSON", "Kowalski")])
    findings = audit_document(document, "Najemcą jest Kowalski.")
    assert len(findings) == 1
    assert findings[0].match_mode == "exact"


def test_structured_id_leaks_despite_formatting():
    document = _doc([("PESEL", "90010112345")])
    findings = audit_document(document, "PESEL wynosi 90010112345 dokładnie.")
    assert len(findings) == 1
    assert findings[0].match_mode == "exact_id"


def test_diacritic_folded_leak_is_caught():
    document = _doc([("PERSON", "Wiśniewski")])
    findings = audit_document(document, "Pan Wisniewski podpisal.")  # accents stripped
    assert len(findings) == 1
    assert findings[0].type == "PERSON"


def test_no_false_leak_on_unrelated_surname():
    document = _doc([("PERSON", "Kowalski")])
    findings = audit_document(document, "Pan Kowalczyk podpisał umowę.")
    assert findings == []


def test_clean_outbound_zero_leaks():
    document = _doc([("PERSON", "Kowalski"), ("PESEL", "90010112345")])
    findings = audit_document(document, "Pan SynteoOsoba podpisał, PESEL 00000000001.")
    assert findings == []


def test_email_year_digit_is_not_a_leak():
    # "adam09@ppuh.com" digits = "09"; a stray "09" in the text must NOT count.
    document = _doc([("EMAIL_ADDRESS", "adam09@ppuh.com")])
    findings = audit_document(document, "Zlecenie nr 09 z dnia 09.")
    assert findings == []


def test_full_email_still_leaks():
    document = _doc([("EMAIL_ADDRESS", "adam09@ppuh.com")])
    findings = audit_document(document, "Kontakt: adam09@ppuh.com proszę pisać.")
    assert len(findings) == 1
    assert findings[0].match_mode == "exact"


def test_date_year_fragment_is_not_a_leak():
    # gold date "21.12.1984"; a different fake date sharing the year 1984 is not a leak.
    document = _doc([("DATE_TIME", "21.12.1984")])
    findings = audit_document(document, "Sporządzono 03.07.1984 w Krakowie.")
    assert findings == []


def test_repeated_mention_counts_as_one_leak():
    # The same name appears twice in the gold (comparycja + signature); a single
    # surviving surface in the outbound must be counted once, not twice.
    document = _doc([("PERSON", "Aniela Potoczna"), ("PERSON", "Aniela Potoczna")])
    findings = audit_document(document, "Sprzedającym jest Aniela Potoczna w sprawie.")
    assert len(findings) == 1


def test_fake_collision_is_masked_out():
    # The gateway replaced "Kornelia Kycia" with the fake "Kornelia Nowak"; the fake
    # first name must not be mistaken for a leak once masked.
    document = _doc([("PERSON", "Kornelia Kycia")])
    outbound = "Sprzedającym jest Kornelia Nowak, zamieszkała w Gdańsku."
    assert audit_document(document, outbound) != []  # naive scan flags it
    assert audit_document(document, outbound, ("Kornelia Nowak",)) == []  # masked: clean
