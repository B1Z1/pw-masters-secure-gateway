def build_pesel(faker, rng, entity=None) -> FakeValue:
    meta = getattr(entity, "metadata", None) or {}
    gender = meta.get("gender") or rng.choice(["male", "female"])
    year = rng.randint(1940, 2010)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return FakeValue(
        entity_type="PESEL",
        base=make_pesel(year, month, day, gender, rng),
        gender=gender,
    )
