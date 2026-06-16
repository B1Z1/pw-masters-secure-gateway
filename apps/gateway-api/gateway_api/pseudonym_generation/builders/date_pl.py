"""DATE_TIME builder (FR-006, research D9).

Uniform ±10-year shift for EVERY date (no birth-vs-non-birth classification).
Output is ``DD.MM.YYYY``. Day/month parsed from the original when possible.
"""

from __future__ import annotations

import re

from ..dto import FakeValue

_YEAR = re.compile(r"(\d{4})")
_DMY = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/]\d{4}")


def build_date(faker, rng, entity=None) -> FakeValue:
    text = getattr(entity, "text", "") or ""
    year_match = _YEAR.search(text)
    year = int(year_match.group(1)) if year_match else rng.randint(1960, 2010)
    new_year = year + rng.randint(-10, 10)

    dmy = _DMY.search(text)
    if dmy:
        day, month = int(dmy.group(1)), int(dmy.group(2))
    else:
        day, month = rng.randint(1, 28), rng.randint(1, 12)
    day = min(max(day, 1), 28)  # clamp to a day valid in every month
    month = min(max(month, 1), 12)

    return FakeValue(
        entity_type="DATE_TIME", base=f"{day:02d}.{month:02d}.{new_year:04d}"
    )
