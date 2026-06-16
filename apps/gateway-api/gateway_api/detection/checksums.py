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
