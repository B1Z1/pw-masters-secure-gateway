"""City + atomic address builders (FR-001/FR-005/FR-019).

A city carries inflection forms (it declines). An address is **atomic** — one
block, ``forms=None``, never internally inflected.
"""

from __future__ import annotations

from ..dto import FakeValue
from ..inflection import Pattern, all_forms, classify


def _declinable_city(faker, rng) -> tuple[str, Pattern]:
    """Pick a city whose pattern declines cleanly (post-filter, like surnames).

    Avoids indeclinable picks (e.g. ``-ice`` plurals) so a fake LOCATION can be
    rendered in the original's case and round-trip correctly.
    """
    for _ in range(10):
        city = faker.city()
        pattern = classify(city, None, kind="city")
        if pattern is not Pattern.INDECLINABLE:
            return city, pattern
    return city, pattern  # give up → base-form fallback (documented limitation)


def build_location(faker, rng, entity=None) -> FakeValue:
    entity_type = getattr(entity, "entity_type", None) or "LOCATION"
    city, pattern = _declinable_city(faker, rng)
    return FakeValue(
        entity_type=entity_type,
        base=city,
        forms=all_forms(city, pattern),
    )


def build_address(faker, rng, entity=None) -> FakeValue:
    base = (
        f"ul. {faker.street_name()} {faker.building_number()}, "
        f"{faker.postcode()} {faker.city()}"
    )
    return FakeValue(entity_type="POLISH_ADDRESS", base=base, forms=None)
