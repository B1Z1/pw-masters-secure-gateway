"""Email + phone builders (FR-005)."""

from __future__ import annotations

from ..dto import FakeValue


def build_email(faker, rng, entity=None) -> FakeValue:
    return FakeValue(entity_type="EMAIL_ADDRESS", base=faker.ascii_email())


def build_phone(faker, rng, entity=None) -> FakeValue:
    # Valid Polish mobile format: 9 digits, leading 5/6/7/8, "+48 XXX XXX XXX".
    digits = str(rng.choice([5, 6, 7, 8])) + "".join(
        str(rng.randint(0, 9)) for _ in range(8)
    )
    base = f"+48 {digits[0:3]} {digits[3:6]} {digits[6:9]}"
    return FakeValue(entity_type="PHONE_NUMBER", base=base)
