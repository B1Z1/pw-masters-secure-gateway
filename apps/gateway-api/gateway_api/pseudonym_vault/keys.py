"""Per-type mapping keys + HMAC forward field names (research D4).

The original value never appears in a Redis field name: the forward index is a
keyed HMAC of the normalized original (non-reversible, resists offline dictionary
attack), and the reverse index uses the synthetic fake form (safe in clear).
"""

from __future__ import annotations

import hashlib
import hmac

from ..pii_detection.normalization import digits_only

_DIGIT_TYPES = frozenset({"PESEL", "NIP", "REGON", "POLISH_BANK_ACCOUNT"})
_NAME_TYPES = frozenset({"PERSON", "LOCATION"})


def mapping_key(entity_type: str, text: str, lemma: str | None = None) -> str:
    """Normalized key for one entity (data-model §5).

    PERSON/LOCATION → spaCy lemma (lowercased); identifiers → digits only
    (separator-insensitive); everything else → whitespace-normalized, case-folded.
    """
    if entity_type in _NAME_TYPES:
        return (lemma or text).strip().lower()
    if entity_type in _DIGIT_TYPES:
        return digits_only(text)
    return " ".join(text.split()).casefold()


def fwd_field(key_bytes: bytes, entity_type: str, mkey: str) -> str:
    """Forward field name = ``fwd:`` + HMAC-SHA256(key, type|mapping_key)."""
    mac = hmac.new(
        key_bytes, f"{entity_type}|{mkey}".encode(), hashlib.sha256
    ).hexdigest()
    return f"fwd:{mac}"
