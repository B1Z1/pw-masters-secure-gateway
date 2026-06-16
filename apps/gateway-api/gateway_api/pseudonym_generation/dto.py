"""Generator output DTO (data-model §2).

The unit produced by ``FakeDataGenerator.generate()``. Stateless — it knows
nothing about sessions; collision avoidance is the MappingStore's job.
"""

from __future__ import annotations

from pydantic import BaseModel


class FakeValue(BaseModel):
    """A realistic synthetic replacement for one detected entity."""

    entity_type: str
    base: str
    # case → form map for PERSON/LOCATION (from inflection.all_forms); None for
    # types that do not inflect (identifiers, dates, email, phone, address).
    forms: dict[str, str] | None = None
    # "male"/"female" for PERSON and PESEL; None otherwise.
    gender: str | None = None
