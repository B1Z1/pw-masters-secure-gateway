"""Polish postal address recognizer (FR-012).

Street + building/flat + postal code (XX-XXX) + city, single- or multi-line;
also a street-less form (postal code + city) at lower confidence. A street that
is a surname (``ul. Kowalskiego``) stays part of the address — the engine's
overlap pass keeps the longer address span and drops any contained PERSON/
LOCATION (research D4, FR-024/FR-025).
"""

from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

from ..scoring import S_ADDRESS_NO_STREET, S_ADDRESS_WITH_STREET
from ._checksum_base import attach_pii_meta

_STREET_PREFIX = r"(?:ul\.|al\.|pl\.|os\.)"
_WORD = r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż.\-]+"
_NAME = rf"{_WORD}(?:\s+{_WORD}){{0,3}}"
_CITY_WORD = r"[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ\-]+"
_CITY = rf"{_CITY_WORD}(?:\s+{_CITY_WORD})?"
_POSTAL = r"\d{2}-\d{3}"
_POSTAL_RE = re.compile(_POSTAL)


class PolishAddressRecognizer(PatternRecognizer):
    ENTITY = "POLISH_ADDRESS"
    PATTERNS = [
        # Street + building/flat, optionally + postal + city (same or next line).
        Pattern(
            "address_full",
            rf"{_STREET_PREFIX}\s+{_NAME}\s+\d+[A-Za-z]?(?:\s*/\s*\d+)?"
            rf"(?:[,\s]+{_POSTAL}\s+{_CITY})?",
            S_ADDRESS_WITH_STREET,
        ),
        # Postal code + city, no street.
        Pattern("address_postal_city", rf"\b{_POSTAL}\s+{_CITY}", S_ADDRESS_NO_STREET),
    ]
    CONTEXT = ["adres", "zamieszkały", "siedziba", "ulica"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="PolishAddressRecognizer",
        )

    def analyze(
        self, text, entities, nlp_artifacts=None, regex_flags: int | None = None
    ):
        results = super().analyze(
            text, entities, nlp_artifacts=nlp_artifacts, regex_flags=regex_flags
        )
        for r in results:
            matched = text[r.start : r.end]
            has_street = bool(re.match(_STREET_PREFIX, matched.strip()))
            postal_match = _POSTAL_RE.search(matched)
            attach_pii_meta(
                r,
                {
                    "has_street": has_street,
                    "postal_code": postal_match.group(0) if postal_match else None,
                },
            )
        return results
