"""Pragmatic Polish declension (research D2, contracts/inflection.md).

Pure Python — **no NLP dependency**. We only ever GENERATE forms from a known
base + classified pattern; the hard direction (arbitrary surface → lemma + case)
is spaCy's job (see pii_detection enrichment). Fixed suffix tables cover the
common patterns; rare/foreign/indeclinable tokens fall back to the base form.

Cases: nom, gen, dat, acc, ins, loc. First name and surname are classified and
declined independently. Documented limitation (Constitution IX): soft-stem and
foreign tokens are approximate or left in base form.
"""

from __future__ import annotations

from enum import StrEnum

CASES = ("nom", "gen", "dat", "acc", "ins", "loc")

_VOWELS = "aeiouyąęó"


class Pattern(StrEnum):
    ADJ_M = "ADJ_M"  # -ski/-cki/-dzki   (Kowalski)
    ADJ_F = "ADJ_F"  # -ska/-cka/-dzka   (Kowalska)
    NOUN_M_CONS = "NOUN_M_CONS"  # consonant-ending masc. (Nowak, Marek, Jan)
    NOUN_F_A = "NOUN_F_A"  # -a ending          (Anna, Anka)
    CITY_M = "CITY_M"  # masc. city         (Kraków, Gdańsk)
    CITY_F = "CITY_F"  # -a city            (Warszawa)
    INDECLINABLE = "INDECLINABLE"


def classify(token: str, gender: str | None = None, kind: str = "person") -> Pattern:
    """Classify a single token into a declension pattern."""
    low = token.lower()
    if not low:
        return Pattern.INDECLINABLE

    if kind == "city":
        if low.endswith("ów"):
            return Pattern.CITY_M
        if low.endswith("a"):
            return Pattern.CITY_F
        if low[-1] not in _VOWELS:
            return Pattern.CITY_M
        return Pattern.INDECLINABLE

    # person
    if low.endswith(("ski", "cki", "dzki")):
        return Pattern.ADJ_M
    if low.endswith(("ska", "cka", "dzka")):
        return Pattern.ADJ_F
    if gender == "female":
        return Pattern.NOUN_F_A if low.endswith("a") else Pattern.INDECLINABLE
    # male or unknown gender
    if low.endswith("a"):
        return Pattern.NOUN_F_A  # masculine -a (Kuba, Barnaba) declines like fem.
    if low[-1] in _VOWELS:  # -o/-e/-i/-y/-u/-ó endings → treat as indeclinable
        return Pattern.INDECLINABLE
    return Pattern.NOUN_M_CONS


def _soften_final(stem: str) -> str:
    """Approximate softening of a final soft consonant before a vowel ending."""
    if stem.endswith("ń"):
        return stem[:-1] + "ni"
    return stem


def decline(token: str, pattern: Pattern, case: str) -> str:
    """Return ``token`` inflected to ``case`` under ``pattern``."""
    if case == "nom" or pattern == Pattern.INDECLINABLE:
        return token

    if pattern == Pattern.ADJ_M:
        stem = token[:-1]  # drop final 'i'
        return (
            stem
            + {"gen": "iego", "dat": "iemu", "acc": "iego", "ins": "im", "loc": "im"}[
                case
            ]
        )

    if pattern == Pattern.ADJ_F:
        stem = token[:-1]  # drop final 'a'
        return (
            stem
            + {"gen": "iej", "dat": "iej", "acc": "ą", "ins": "ą", "loc": "iej"}[case]
        )

    if pattern == Pattern.NOUN_F_A:
        stem = token[:-1]
        last = stem[-1].lower() if stem else ""
        if case == "gen":
            return stem + ("i" if last in "kg" else "y")
        if case in ("dat", "loc"):
            if last == "k":
                return stem[:-1] + "ce"
            if last == "g":
                return stem[:-1] + "dze"
            return _soften_final(stem) + "e" if stem.endswith("ń") else stem + "ie"
        if case == "acc":
            return stem + "ę"
        if case == "ins":
            return stem + "ą"

    if pattern == Pattern.NOUN_M_CONS:
        stem = token[:-2] + token[-1] if token.lower().endswith("ek") else token
        last = stem[-1].lower()
        if case in ("gen", "acc"):  # animate masc.: acc == gen
            return _soften_final(stem) + "a" if stem.endswith("ń") else stem + "a"
        if case == "dat":
            return stem + "owi"
        if case == "ins":
            return stem + ("iem" if last in "kg" else "em")
        if case == "loc":
            if last in "kg" or stem.lower().endswith("ch"):
                return stem + "u"
            return _soften_final(stem) + "u" if stem.endswith("ń") else stem + "ie"

    if pattern == Pattern.CITY_M:
        stem = token[:-2] + "ow" if token.lower().endswith("ów") else token
        last = stem[-1].lower()
        if case == "gen":
            return stem + "a"
        if case == "dat":
            return stem + "owi"
        if case == "acc":  # inanimate: acc == nom
            return token
        if case == "ins":
            return stem + ("iem" if last in "kg" else "em")
        if case == "loc":
            if last in "kg" or stem.lower().endswith("ch"):
                return stem + "u"
            return _soften_final(stem) + "u" if stem.endswith("ń") else stem + "ie"

    if pattern == Pattern.CITY_F:
        stem = token[:-1]
        last = stem[-1].lower() if stem else ""
        if case == "gen":
            return stem + ("i" if last in "kg" else "y")
        if case in ("dat", "loc"):
            if last == "k":
                return stem[:-1] + "ce"
            if last == "g":
                return stem[:-1] + "dze"
            return stem + "ie"
        if case == "acc":
            return stem + "ę"
        if case == "ins":
            return stem + "ą"

    return token


def all_forms(token: str, pattern: Pattern) -> dict[str, str]:
    """Map every case to ``token`` inflected under ``pattern``."""
    return {
        grammatical_case: decline(token, pattern, grammatical_case)
        for grammatical_case in CASES
    }
