def person_forms(first: str, last: str, gender: str) -> dict[str, str]:
    """Odmienia imię i nazwisko niezależnie, a następnie łączy je w każdym przypadku."""
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
