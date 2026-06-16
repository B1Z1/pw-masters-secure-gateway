"""Inflection patterns across the six cases + fallbacks (T038, FR-016/018/020)."""

from __future__ import annotations

from gateway_api.pseudonym_generation.builders.person import person_forms
from gateway_api.pseudonym_generation.inflection import (
    CASES,
    Pattern,
    all_forms,
    classify,
)


def _forms(token, gender=None, kind="person"):
    return all_forms(token, classify(token, gender, kind=kind))


def test_adjectival_masculine():
    f = _forms("Kowalski", "male")
    assert f["gen"] == "Kowalskiego"
    assert f["dat"] == "Kowalskiemu"
    assert f["acc"] == "Kowalskiego"
    assert f["ins"] == "Kowalskim"
    assert f["loc"] == "Kowalskim"


def test_adjectival_feminine():
    f = _forms("Kowalska", "female")
    assert f["gen"] == "Kowalskiej"
    assert f["acc"] == "Kowalską"
    assert f["ins"] == "Kowalską"


def test_noun_masculine_consonant():
    f = _forms("Nowak", "male")
    assert f["gen"] == "Nowaka"
    assert f["dat"] == "Nowakowi"
    assert f["ins"] == "Nowakiem"
    assert f["loc"] == "Nowaku"


def test_fleeting_e():
    f = _forms("Marek", "male")
    assert f["gen"] == "Marka"
    assert f["ins"] == "Markiem"


def test_noun_feminine_a():
    f = _forms("Anna", "female")
    assert f["gen"] == "Anny"
    assert f["dat"] == "Annie"
    assert f["acc"] == "Annę"
    assert f["ins"] == "Anną"


def test_kg_softening():
    f = _forms("Anka", "female")
    assert f["gen"] == "Anki"
    assert f["dat"] == "Ance"
    assert f["loc"] == "Ance"


def test_city_ow():
    f = _forms("Kraków", kind="city")
    assert f["gen"] == "Krakowa"
    assert f["loc"] == "Krakowie"
    assert f["acc"] == "Kraków"  # inanimate: acc == nom


def test_city_consonant():
    assert _forms("Gdańsk", kind="city")["loc"] == "Gdańsku"


def test_city_feminine():
    f = _forms("Warszawa", kind="city")
    assert f["loc"] == "Warszawie"
    assert f["acc"] == "Warszawę"


def test_indeclinable_foreign_endings():
    p = classify("Linde", "male")  # ends in a vowel → indeclinable
    assert p is Pattern.INDECLINABLE
    assert all(v == "Linde" for v in all_forms("Linde", p).values())


def test_female_consonant_surname_indeclinable():
    assert classify("Nowak", "female") is Pattern.INDECLINABLE


def test_first_and_last_inflect_independently():
    # "Jan Kowalski" genitive = gen(Jan) + gen(Kowalski)
    assert person_forms("Jan", "Kowalski", "male")["gen"] == "Jana Kowalskiego"


def test_all_six_cases_present():
    assert set(_forms("Nowak", "male")) == set(CASES)
