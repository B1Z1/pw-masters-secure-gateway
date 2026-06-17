"""Fuzzy fallback restore (US3): bounded, PERSON/LOCATION-only, base-form.

Unit tests of the pure ``FuzzyNameRestorer`` plus store-level wiring through
``restore_text(..., fuzzy=True)``. Covers recovery of an unforeseen inflected
form, exact-only enforcement on identifiers, prefix-anchor rejection, the
invented-name passthrough, tie-skip, the min-length gate, and that an
already-restored original is not re-touched (FR-008..FR-015).
"""

from __future__ import annotations

from gateway_api.pseudonym_generation.inflection import all_forms, classify
from gateway_api.pseudonym_vault.fuzzy_restoration import FuzzyNameRestorer


def _person(orig_base: str, fake_base: str) -> dict:
    forms = list(all_forms(fake_base, classify(fake_base, None)).values())
    return {
        "entity_type": "PERSON",
        "orig_base": orig_base,
        "fake_base": fake_base,
        "fake_forms": forms,
    }


# --- pure FuzzyNameRestorer --------------------------------------------------


def test_recovers_unforeseen_inflection_in_base_form():
    record = _person("Kowalski", "Nowak")
    # "Nowakach" is not a generated case form; within edit distance 2 of "Nowaka".
    out = FuzzyNameRestorer().restore("Sprawa Nowakach trwa.", [record])
    assert out == "Sprawa Kowalski trwa."


def test_identifier_like_token_not_touched():
    record = _person("Kowalski", "Nowak")
    text = "Numer 12345678901 oraz adres x@y.pl bez zmian."
    assert FuzzyNameRestorer().restore(text, [record]) == text


def test_prefix_anchor_rejects_lookalike():
    record = _person("Kowalski", "Nowak")
    # "Nowela" is within distance 2 of "Nowaka" but shares only "now" (ratio 0.5)
    # → the prefix anchor rejects it before the distance gate.
    text = "To slowo Nowela."
    assert FuzzyNameRestorer().restore(text, [record]) == text


def test_invented_name_passthrough():
    record = _person("Kowalski", "Nowak")
    text = "Pojawił się Zygmunt August."
    assert FuzzyNameRestorer().restore(text, [record]) == text


def test_unresolvable_tie_is_skipped():
    record_a = {
        "entity_type": "PERSON",
        "orig_base": "Adamski",
        "fake_base": "Kowal",
        "fake_forms": ["Kowal"],
    }
    record_b = {
        "entity_type": "PERSON",
        "orig_base": "Bielski",
        "fake_base": "Kowak",
        "fake_forms": ["Kowak"],
    }
    # "Kowat" is distance 1 from both, to DIFFERENT originals → skip (never guess).
    out = FuzzyNameRestorer().restore("Pan Kowat dzwonił.", [record_a, record_b])
    assert out == "Pan Kowat dzwonił."


def test_token_shorter_than_minimum_not_matched():
    record = {
        "entity_type": "PERSON",
        "orig_base": "Kowalski",
        "fake_base": "Now",
        "fake_forms": ["Now", "Nowa"],
    }
    assert FuzzyNameRestorer().restore("To Now.", [record]) == "To Now."


def test_already_restored_original_not_retouched():
    record = _person("Kowalski", "Nowak")
    # An original already in the text (different stem from the fake) is left alone.
    text = "Pan Kowalski wrócił."
    assert FuzzyNameRestorer().restore(text, [record]) == text


def test_location_single_token_recovered():
    forms = list(all_forms("Gdańsk", classify("Gdańsk", None, kind="city")).values())
    record = {
        "entity_type": "LOCATION",
        "orig_base": "Kraków",
        "fake_base": "Gdańsk",
        "fake_forms": forms,
    }
    # "Gdańskach" — unforeseen, within distance 2 of "Gdańska".
    out = FuzzyNameRestorer().restore("Były w Gdańskach.", [record])
    assert out == "Były w Kraków."


# --- store-level wiring (restore_text fuzzy flag) ----------------------------


async def test_restore_text_fuzzy_recovers_bare_surname(make_store, make_entity):
    store = make_store(seed=7)
    fake_nominative = await store.get_or_create(
        "fz", make_entity("PERSON", "Kowalski", lemma="Kowalski", case="nom")
    )
    # A bare surname-only mention: the exact pass only matches the full stored
    # surfaces ("First Last"), so it leaves a standalone surname untouched; the
    # fuzzy fallback recovers it (FR-008).
    surname = fake_nominative.split()[-1]
    text = f"Pan {surname} przyszedł."

    exact_only = await store.restore_text("fz", text, fuzzy=False)
    assert "Kowalski" not in exact_only

    with_fuzzy = await store.restore_text("fz", text, fuzzy=True)
    assert "Kowalski" in with_fuzzy


async def test_fuzzy_never_touches_identifier(make_store, make_entity):
    store = make_store(seed=7)
    fake_pesel = await store.get_or_create(
        "fp", make_entity("PESEL", "90010112345", metadata={"gender": "male"})
    )
    perturbed = fake_pesel[:-1] + ("0" if fake_pesel[-1] != "0" else "1")

    restored = await store.restore_text("fp", f"Numer {perturbed}.", fuzzy=True)

    # Exact-only: the perturbed fake is left as-is; the real PESEL is NOT injected.
    assert perturbed in restored
    assert "90010112345" not in restored
