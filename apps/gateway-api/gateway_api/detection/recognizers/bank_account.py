"""Polish bank account recognizer (FR-011): NRB / IBAN, 26 digits, mod-97."""

from __future__ import annotations

from presidio_analyzer import Pattern

from ..checksums import nrb_is_valid
from ..normalization import digits_only
from ..scoring import S_INVALID
from ._checksum_base import ChecksumPatternRecognizer


class PolishBankAccountRecognizer(ChecksumPatternRecognizer):
    ENTITY = "POLISH_BANK_ACCOUNT"
    PATTERNS = [
        # PL-prefixed or bare, contiguous 26 digits.
        Pattern("nrb_plain", r"\b(?:PL)?\d{26}\b", S_INVALID),
        # Spaced 2+4×6 grouping, optional PL prefix.
        Pattern("nrb_spaced", r"\b(?:PL[ ]?)?\d{2}(?:[ ]\d{4}){6}\b", S_INVALID),
    ]
    CONTEXT = ["rachunek", "konto", "iban", "nr"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="PolishBankAccountRecognizer",
        )

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        fmt = "IBAN" if normalized.upper().startswith("PL") else "NRB"
        digits = digits_only(normalized)
        valid = nrb_is_valid(digits)
        return valid, {"format": fmt, "normalized": digits, "mod97_valid": valid}
