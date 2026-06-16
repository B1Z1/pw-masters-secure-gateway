"""Pure Polish identifier checksum & derivation logic (research "checksum algorithms").

No Presidio / spaCy dependency — fully unit-testable in isolation. All functions
take an already-normalized (digits-only) string and never raise.
"""

from __future__ import annotations

import datetime

# --- PESEL -----------------------------------------------------------------

PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def pesel_is_valid(d: str) -> bool:
    """Validate the 11-digit PESEL control sum."""
    if len(d) != 11 or not d.isdigit():
        return False
    total = sum(int(c) * w for c, w in zip(d[:10], PESEL_WEIGHTS, strict=False))
    control = (10 - (total % 10)) % 10
    return control == int(d[10])


def pesel_gender(d: str) -> str | None:
    """Gender from the 10th digit (index 9): even = female, odd = male."""
    if len(d) != 11 or not d.isdigit():
        return None
    return "female" if int(d[9]) % 2 == 0 else "male"


def pesel_birth_date(d: str) -> str | None:
    """Birth date (ISO) from a PESEL, honouring the post-2000 month offset.

    Month encodes the century: 01-12→1900s, 21-32→2000s, 41-52→2100s,
    61-72→2200s, 81-92→1800s. Returns ``None`` for an incoherent date.
    """
    if len(d) != 11 or not d.isdigit():
        return None
    yy, mm, dd = int(d[0:2]), int(d[2:4]), int(d[4:6])
    if 1 <= mm <= 12:
        century, month = 1900, mm
    elif 21 <= mm <= 32:
        century, month = 2000, mm - 20
    elif 41 <= mm <= 52:
        century, month = 2100, mm - 40
    elif 61 <= mm <= 72:
        century, month = 2200, mm - 60
    elif 81 <= mm <= 92:
        century, month = 1800, mm - 80
    else:
        return None
    try:
        return datetime.date(century + yy, month, dd).isoformat()
    except ValueError:
        return None


# --- NIP --------------------------------------------------------------------

NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def nip_is_valid(d: str) -> bool:
    """Validate the 10-digit NIP control sum. A leading 0 is valid (FR-009)."""
    if len(d) != 10 or not d.isdigit():
        return False
    control = sum(int(c) * w for c, w in zip(d[:9], NIP_WEIGHTS, strict=False)) % 11
    if control == 10:
        return False
    return control == int(d[9])


# --- REGON ------------------------------------------------------------------

REGON9_WEIGHTS = (8, 9, 2, 3, 4, 5, 6, 7)
REGON14_WEIGHTS = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def _regon_control(d: str, weights: tuple[int, ...]) -> int:
    control = sum(int(c) * w for c, w in zip(d, weights, strict=False)) % 11
    return 0 if control == 10 else control


def regon9_is_valid(d: str) -> bool:
    if len(d) != 9 or not d.isdigit():
        return False
    return _regon_control(d[:8], REGON9_WEIGHTS) == int(d[8])


def regon14_is_valid(d: str) -> bool:
    if len(d) != 14 or not d.isdigit():
        return False
    return _regon_control(d[:13], REGON14_WEIGHTS) == int(d[13])


# --- Bank account (NRB / IBAN, ISO 7064 mod-97) -----------------------------


def nrb_is_valid(d: str) -> bool:
    """Validate a 26-digit Polish NRB via the IBAN mod-97 check (ISO 7064).

    IBAN = ``PL`` + 26 digits. Move the 4 leading IBAN chars to the end and
    replace letters (P=25, L=21): ``digits[2:] + "2521" + digits[:2]`` mod 97 == 1.
    """
    if len(d) != 26 or not d.isdigit():
        return False
    rearranged = d[2:] + "2521" + d[:2]
    return int(rearranged) % 97 == 1


# --- Generation helpers (Epic 3) --------------------------------------------
# Reuse the weight tuples above so generation and validation share one source of
# truth. Each returns a control digit / check digits that make the value pass the
# corresponding ``*_is_valid`` check.


def pesel_control_digit(d10: str) -> int:
    """Control digit (11th) for the first 10 PESEL digits."""
    total = sum(int(c) * w for c, w in zip(d10, PESEL_WEIGHTS, strict=False))
    return (10 - (total % 10)) % 10


def nip_control_digit(d9: str) -> int:
    """NIP control digit for 9 digits. May be 10 (invalid) — caller must re-roll."""
    return sum(int(c) * w for c, w in zip(d9, NIP_WEIGHTS, strict=False)) % 11


def regon9_control_digit(d8: str) -> int:
    """REGON-9 control digit for the first 8 digits."""
    return _regon_control(d8, REGON9_WEIGHTS)


def regon14_control_digit(d13: str) -> int:
    """REGON-14 control digit for the first 13 digits."""
    return _regon_control(d13, REGON14_WEIGHTS)


def nrb_check_digits(bban24: str) -> str:
    """Two leading NRB check digits so the 26-digit account passes mod-97."""
    base = int(bban24 + "2521" + "00") % 97
    return f"{(1 - base) % 97:02d}"


def make_pesel(year: int, month: int, day: int, gender: str, rng) -> str:
    """Build a valid PESEL encoding the given birth date + gender (research D6).

    Century encoded in the month offset (post-2000 → +20, etc.). The gender digit
    (index 9) parity: even = female, odd = male.
    """
    if 2000 <= year <= 2099:
        mm = month + 20
    elif 2100 <= year <= 2199:
        mm = month + 40
    elif 2200 <= year <= 2299:
        mm = month + 60
    elif 1800 <= year <= 1899:
        mm = month + 80
    else:  # 1900-1999
        mm = month
    d6 = f"{year % 100:02d}{mm:02d}{day:02d}"
    serial = f"{rng.randint(0, 999):03d}"
    g = rng.randint(0, 9)
    if gender == "female":
        if g % 2 == 1:
            g = (g - 1) % 10
    elif g % 2 == 0:
        g = (g + 1) % 10
    d10 = d6 + serial + str(g)
    return d10 + str(pesel_control_digit(d10))
