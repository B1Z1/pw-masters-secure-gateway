"""PERSON builder (FR-001/FR-002). Gendered name; declinable surname; case forms.

Gender is RANDOM — we deliberately do NOT associate the name with a nearby PESEL
(documented limitation, Constitution IX). The surname is post-filtered to a
declinable pattern so inflection stays clean.
"""

from __future__ import annotations

from ..dto import FakeValue
from ..inflection import CASES, Pattern, classify, decline


def _declinable_surname(faker, rng, gender: str) -> str:
    pick = faker.last_name_female if gender == "female" else faker.last_name_male
    for _ in range(10):
        surname = pick()
        if classify(surname, gender) is not Pattern.INDECLINABLE:
            return surname
    return surname  # give up after retries — base-form fallback applies on use


def person_forms(first: str, last: str, gender: str) -> dict[str, str]:
    """Inflect first name and surname independently, then join per case."""
    first_pattern = classify(first, gender)
    last_pattern = classify(last, gender)
    return {
        grammatical_case: (
            f"{decline(first, first_pattern, grammatical_case)} "
            f"{decline(last, last_pattern, grammatical_case)}"
        )
        for grammatical_case in CASES
    }


def build_person(faker, rng, entity=None) -> FakeValue:
    gender = rng.choice(["male", "female"])
    pick_first = (
        faker.first_name_female if gender == "female" else faker.first_name_male
    )
    first = pick_first()
    last = _declinable_surname(faker, rng, gender)
    return FakeValue(
        entity_type="PERSON",
        base=f"{first} {last}",
        forms=person_forms(first, last, gender),
        gender=gender,
    )
