"""Normalization helpers (research D, FR-003/FR-013).

Validation runs on the *normalized* value (separators stripped), but detection
results always reference the original span exactly as written — these helpers
never change offsets, they only produce a value to validate.
"""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[ \-]")
_NON_DIGIT = re.compile(r"\D")


def strip_separators(text: str) -> str:
    """Remove spaces and dashes (PESEL/NIP/REGON before checksum validation)."""
    return _SEPARATORS.sub("", text)


def digits_only(text: str) -> str:
    """Keep only digits (bank account: drops an optional ``PL`` prefix + spaces)."""
    return _NON_DIGIT.sub("", text)
