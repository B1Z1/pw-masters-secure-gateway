"""Polish date recognizer (FR-004 DATE_TIME): numeric + worded (genitive months).

The stock Presidio date recognizer is English-oriented (Constitution VI), so this
custom recognizer handles ``12.01.2024`` / ``12-01-2024`` and ``12 stycznia 2024 r.``.
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from ..scoring import S_DATE_NUMERIC, S_DATE_WORDED
from ._checksum_base import attach_pii_meta

_MONTHS = (
    "stycznia|lutego|marca|kwietnia|maja|czerwca|"
    "lipca|sierpnia|września|października|listopada|grudnia"
)


class DateRecognizer(PatternRecognizer):
    ENTITY = "DATE_TIME"
    PATTERNS = [
        Pattern("date_numeric", r"\b\d{1,2}[.\-]\d{1,2}[.\-]\d{4}\b", S_DATE_NUMERIC),
        Pattern(
            "date_worded",
            rf"\b\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}(?:\s*r\.)?",
            S_DATE_WORDED,
        ),
    ]
    CONTEXT = ["data", "dnia"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="DateRecognizer",
        )

    def analyze(
        self, text, entities, nlp_artifacts=None, regex_flags: int | None = None
    ):
        results = super().analyze(
            text, entities, nlp_artifacts=nlp_artifacts, regex_flags=regex_flags
        )
        lowered_months = _MONTHS.split("|")
        for r in results:
            matched = text[r.start : r.end].lower()
            kind = "worded" if any(m in matched for m in lowered_months) else "numeric"
            attach_pii_meta(r, {"kind": kind})
        return results
