"""NIP recognizer (FR-009). Leading 0 is valid; common dashed groupings supported."""

from __future__ import annotations

from presidio_analyzer import Pattern

from ..checksums import nip_is_valid
from ..scoring import S_INVALID
from ._checksum_base import ChecksumPatternRecognizer


class NipRecognizer(ChecksumPatternRecognizer):
    ENTITY = "NIP"
    PATTERNS = [
        Pattern("nip_plain", r"\b\d{10}\b", S_INVALID),
        Pattern("nip_dashed_3322", r"\b\d{3}-\d{3}-\d{2}-\d{2}\b", S_INVALID),
        Pattern("nip_dashed_3223", r"\b\d{3}-\d{2}-\d{2}-\d{3}\b", S_INVALID),
    ]
    CONTEXT = ["nip", "vat"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="NipRecognizer",
        )

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        return nip_is_valid(normalized), {}
