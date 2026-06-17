"""Checksum-scored pattern recognizer base (research D3).

Presidio's ``validate_result`` contract drops a match when it returns ``False``
(score set to ``MIN_SCORE`` and filtered out). FR-014 requires bad-checksum
values to be *surfaced at low confidence, not dropped*. So instead of
``validate_result``, we run the regex via the base class and then assign the
score explicitly (valid → ``S_VALID``, invalid → ``S_INVALID``) and attach
metadata. The context enhancer adds its bonus afterwards.
"""

from __future__ import annotations

from presidio_analyzer import PatternRecognizer, RecognizerResult

from ..normalization import strip_separators
from ..scoring import S_INVALID, S_VALID


def attach_pii_meta(result: RecognizerResult, meta: dict) -> None:
    """Stash detection-time metadata on a result under ``recognition_metadata['pii']``.

    Shared by checksum and non-checksum (date/address) recognizers; the engine
    reads this key when mapping to ``DetectedEntity`` (research D7).
    """
    existing = getattr(result, "recognition_metadata", None)
    rm = dict(existing) if isinstance(existing, dict) else {}
    rm["pii"] = dict(meta)
    result.recognition_metadata = rm


class ChecksumPatternRecognizer(PatternRecognizer):
    """Base for PESEL/NIP/REGON/bank recognizers — checksum drives the score."""

    def analyze(
        self,
        text: str,
        entities,
        nlp_artifacts=None,
        regex_flags: int | None = None,
    ):
        results = super().analyze(
            text, entities, nlp_artifacts=nlp_artifacts, regex_flags=regex_flags
        )
        for result in results:
            normalized = strip_separators(text[result.start : result.end])
            valid, meta = self.validate_checksum(normalized)
            result.score = S_VALID if valid else S_INVALID
            meta = dict(meta or {})
            meta.setdefault("normalized", normalized)
            meta["checksum_valid"] = valid
            attach_pii_meta(result, meta)
        return results

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        """Return ``(is_valid, metadata)`` for the normalized value. Override."""
        raise NotImplementedError
