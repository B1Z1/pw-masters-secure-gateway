"""Canonical gold entity vocabulary + the gateway-label alias map (research D8).

The gold standard speaks ten canonical types. The gateway emits its own recognizer
labels (``POLISH_ADDRESS``, ``POLISH_BANK_ACCOUNT``, ``NRB``, ``IBAN``,
``ORGANIZATION`` …). ``normalize_label`` reconciles a gateway label to the canonical
vocabulary, or returns ``None`` for an unmapped label. An unmapped predicted span is
surfaced in the report AND counted as a false positive (see ``detection_metrics``),
so precision stays conservative.
"""

from __future__ import annotations

CANONICAL_TYPES: tuple[str, ...] = (
    "PERSON",
    "LOCATION",
    "ADDRESS",
    "PESEL",
    "NIP",
    "REGON",
    "BANK_ACCOUNT",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "DATE_TIME",
)

# Versioned map: gateway-emitted label -> canonical gold type (research D8).
GATEWAY_LABEL_ALIASES: dict[str, str] = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "POLISH_ADDRESS": "ADDRESS",
    "ADDRESS": "ADDRESS",
    "PESEL": "PESEL",
    "NIP": "NIP",
    "REGON": "REGON",
    "POLISH_BANK_ACCOUNT": "BANK_ACCOUNT",
    "BANK_ACCOUNT": "BANK_ACCOUNT",
    "NRB": "BANK_ACCOUNT",
    "IBAN": "BANK_ACCOUNT",
    "IBAN_CODE": "BANK_ACCOUNT",
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "DATE_TIME": "DATE_TIME",
}

# Structured identifiers are matched by their normalized exact value in the leak
# audit (digits-only for numeric IDs), never by an inflectional stem (D4).
STRUCTURED_TYPES: frozenset[str] = frozenset(
    {"PESEL", "NIP", "REGON", "BANK_ACCOUNT", "EMAIL_ADDRESS", "PHONE_NUMBER"}
)


def normalize_label(label: str) -> str | None:
    """Return the canonical gold type for a gateway label, or ``None`` if unmapped."""
    return GATEWAY_LABEL_ALIASES.get(label)


def is_structured(canonical_type: str) -> bool:
    """True for identifier-like types matched by exact normalized value (not stem)."""
    return canonical_type in STRUCTURED_TYPES
