def build_location(faker, rng, entity=None) -> FakeValue:
    entity_type = getattr(entity, "entity_type", None) or "LOCATION"
    city, pattern = _declinable_city(faker, rng)
    return FakeValue(
        entity_type=entity_type,
        base=city,
        forms=all_forms(city, pattern),
    )
