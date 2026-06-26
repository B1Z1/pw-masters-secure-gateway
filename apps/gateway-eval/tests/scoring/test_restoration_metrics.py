"""T017 — restoration outcomes + document exact-restore rate."""

from __future__ import annotations

from gateway_eval.scoring.restoration_metrics import (
    aggregate_restoration,
    classify_one,
)


def _classify(original, restored, *, entity_type="PERSON", start=0, end=None):
    end = end if end is not None else len(original)
    return classify_one(
        original=original,
        entity_type=entity_type,
        start=start,
        end=end,
        original_text=original,
        restored_text=restored,
    )


def test_exact_at_position():
    outcome, surface, position = _classify("Jan Kowalski", "Jan Kowalski")
    assert (outcome, surface, position) == ("exact", "Jan Kowalski", True)


def test_correct_inflection_when_only_inflected_form_present():
    # gold base form "Kowalski"; restored text carries the inflected "Kowalskiego"
    outcome, surface, _ = _classify(
        "Kowalski", "Pozdrawiam pana Kowalskiego serdecznie."
    )
    assert outcome == "correct_inflection"
    assert surface == "Kowalskiego"


def test_base_form_only_when_gateway_returns_lemma():
    # gold inflected "Kowalskiego"; restored gives the base "Kowalski"
    outcome, surface, _ = _classify(
        "Kowalskiego", "Umowa z panem Kowalski zawarta."
    )
    assert outcome == "base_form_only"
    assert surface == "Kowalski"


def test_fuzzy_recovered_for_near_miss():
    outcome, surface, _ = _classify("Kowalski", "Pan Kowaski podpisał.")
    assert outcome == "fuzzy_recovered"


def test_missed_when_absent():
    outcome, surface, position = _classify("Kowalski", "Brak nazwiska tutaj.")
    assert outcome == "missed"
    assert surface is None


def test_structured_id_exact_only():
    outcome, _, _ = _classify(
        "90010112345", "PESEL: 90010112345.", entity_type="PESEL"
    )
    assert outcome == "exact"
    missed, _, _ = _classify(
        "90010112345", "PESEL: 11111111111.", entity_type="PESEL"
    )
    assert missed == "missed"


def test_aggregate_doc_exact_rate():
    from gateway_eval.reporting.result_models import RestorationDetail

    details = {
        "d1": [
            RestorationDetail(doc_id="d1", type="PERSON", original="A", outcome="exact", position_correct=True),
            RestorationDetail(doc_id="d1", type="PESEL", original="1", outcome="exact", position_correct=True),
        ],
        "d2": [
            RestorationDetail(doc_id="d2", type="PERSON", original="B", outcome="missed", position_correct=False),
        ],
    }
    report = aggregate_restoration(details)
    assert report.doc_exact_restore_rate == 0.5
    assert report.by_outcome["exact"] == 2
    assert report.by_outcome["missed"] == 1
