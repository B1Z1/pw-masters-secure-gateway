"""REGON recognizer (FR-010). 9- and 14-digit variants, each its own control sum."""

from __future__ import annotations

from presidio_analyzer import Pattern

from ..checksums import regon9_is_valid, regon14_is_valid
from ..scoring import S_INVALID
from ._checksum_base import ChecksumPatternRecognizer


class RegonRecognizer(ChecksumPatternRecognizer):
    ENTITY = "REGON"
    # 14-digit pattern first so the longer span is preferred at match time;
    # the engine's overlap pass is the authoritative guarantee (research D4).
    PATTERNS = [
        Pattern("regon14", r"\b\d{14}\b", S_INVALID),
        Pattern("regon9", r"\b\d{9}\b", S_INVALID),
    ]
    CONTEXT = ["regon"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="RegonRecognizer",
        )

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        if len(normalized) == 14:
            return regon14_is_valid(normalized), {"variant": "14"}
        if len(normalized) == 9:
            return regon9_is_valid(normalized), {"variant": "9"}
        return False, {"variant": None}
