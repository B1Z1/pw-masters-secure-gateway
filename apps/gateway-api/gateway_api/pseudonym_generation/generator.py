"""FakeDataGenerator — stateless dispatch over per-type builders (research D6/D9).

Built on Faker(``pl_PL``) (Constitution VII). Deterministic with an injectable
seed (reproducible tests); random in production. Collision avoidance is the
MappingStore's job — this object just produces one valid value per call.
"""

from __future__ import annotations

import random

from faker import Faker

from ..pii_detection.dto import DetectedEntity
from .builders import contact, date_pl, identifiers, location, person
from .dto import FakeValue

_DISPATCH = {
    "PERSON": person.build_person,
    "LOCATION": location.build_location,
    "POLISH_ADDRESS": location.build_address,
    "EMAIL_ADDRESS": contact.build_email,
    "PHONE_NUMBER": contact.build_phone,
    "DATE_TIME": date_pl.build_date,
    "PESEL": identifiers.build_pesel,
    "NIP": identifiers.build_nip,
    "REGON": identifiers.build_regon,
    "POLISH_BANK_ACCOUNT": identifiers.build_bank_account,
}


class FakeDataGenerator:
    """Produces a realistic Polish ``FakeValue`` for a detected entity."""

    def __init__(self, seed: int | None = None) -> None:
        self._faker = Faker("pl_PL")
        self._rng = random.Random(seed)
        if seed is not None:
            self._faker.seed_instance(seed)

    def generate(self, entity: DetectedEntity) -> FakeValue:
        builder = _DISPATCH.get(entity.entity_type)
        if builder is None:
            # Unknown type: no realistic generator — echo the original unchanged.
            return FakeValue(entity_type=entity.entity_type, base=entity.text)
        return builder(self._faker, self._rng, entity)
