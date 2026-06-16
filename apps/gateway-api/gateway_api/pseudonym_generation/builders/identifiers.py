"""Polish national identifier builders — all checksum-valid (FR-003/FR-004).

Reuses the Epic 2 ``pii_detection.checksums`` generation helpers so a fake passes
the same ``*_is_valid`` check the detector uses.
"""

from __future__ import annotations

from ...pii_detection.checksums import (
    make_pesel,
    nip_control_digit,
    nrb_check_digits,
    regon9_control_digit,
    regon14_control_digit,
)
from ..dto import FakeValue


def _digits(rng, n: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


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


def build_nip(faker, rng, entity=None) -> FakeValue:
    while True:
        d9 = _digits(rng, 9)
        control = nip_control_digit(d9)
        if control != 10:  # 10 is not a valid NIP control digit
            return FakeValue(entity_type="NIP", base=d9 + str(control))


def build_regon(faker, rng, entity=None) -> FakeValue:
    meta = getattr(entity, "metadata", None) or {}
    if "14" in str(meta.get("variant") or "9"):
        d13 = _digits(rng, 13)
        base = d13 + str(regon14_control_digit(d13))
    else:
        d8 = _digits(rng, 8)
        base = d8 + str(regon9_control_digit(d8))
    return FakeValue(entity_type="REGON", base=base)


def build_bank_account(faker, rng, entity=None) -> FakeValue:
    bban = _digits(rng, 24)
    return FakeValue(
        entity_type="POLISH_BANK_ACCOUNT",
        base=nrb_check_digits(bban) + bban,
    )
