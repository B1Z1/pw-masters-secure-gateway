"""PESEL recognizer (FR-008)."""

from __future__ import annotations

from presidio_analyzer import Pattern

from ..checksums import pesel_birth_date, pesel_gender, pesel_is_valid
from ..scoring import S_INVALID
from ._checksum_base import ChecksumPatternRecognizer


class PeselRecognizer(ChecksumPatternRecognizer):
    ENTITY = "PESEL"
    PATTERNS = [Pattern("pesel", r"\b\d{11}\b", S_INVALID)]
    CONTEXT = ["pesel"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="PeselRecognizer",
        )

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        valid = pesel_is_valid(normalized)
        meta = {
            "gender": pesel_gender(normalized),
            "birth_date": pesel_birth_date(normalized),
        }
        return valid, meta
