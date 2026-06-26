"""PII-leak audit on the gateway's outbound text (FR-020/FR-021, research D4).

For every gold original, scan the outbound (pseudonymized) text for ANY surviving
occurrence — and count inflected / partial forms (``Kowalski`` → ``Kowalskiego``) as a
FULL leak. The pass bar is zero leaks (Constitution I/VIII).

Collision control: the outbound text is full of synthetic values drawn from the SAME
Polish Faker pool as the originals, so a fake can coincidentally equal/share a stem
with an original. Before scanning, the gateway's self-declared synthetic insertions
(``entities_replaced`` / ``input_anonymization.replacements``) are MASKED out — this is
not using gateway output as the leak oracle (the gold original is still the sole
ground truth), it only avoids miscounting the gateway's own fakes as leaks. Matching
is type-aware: numeric IDs by digits, e-mail/date by full string, names/places by
exact-or-inflected stem. Documented limitation: D4.
"""

from __future__ import annotations

import re

from ..corpus.gold_standard import GoldDocument
from ..reporting.result_models import LeakFinding, LeakReport
from .surface_matching import fold_diacritics, normalize, shares_stem, tokens

_MIN_STEM_LENGTH = 4
_DIGITS = re.compile(r"\d+")
_MASK_CHAR = "\x00"

# Identifiers matched by their digits only (formatting-insensitive).
_NUMERIC_ID_TYPES = frozenset(
    {"PESEL", "NIP", "REGON", "BANK_ACCOUNT", "PHONE_NUMBER"}
)
# Matched by the full normalized string (no digit/stem shortcuts).
_EXACT_STRING_TYPES = frozenset({"EMAIL_ADDRESS", "DATE_TIME"})


def _digits_only(text: str) -> str:
    return "".join(_DIGITS.findall(text))


def _mask_fakes(text: str, fake_values: tuple[str, ...]) -> str:
    """Blank out the gateway's declared synthetic insertions (longest first)."""
    masked = text
    unique_fakes = sorted(
        {value for value in fake_values if value}, key=len, reverse=True
    )
    for fake in unique_fakes:
        masked = re.sub(
            re.escape(fake),
            lambda match: _MASK_CHAR * len(match.group()),
            masked,
            flags=re.IGNORECASE,
        )
    return masked


def _find_case_insensitive(haystack: str, needle: str) -> tuple[int, int]:
    if not needle:
        return -1, -1
    lowered_index = haystack.lower().find(needle.lower())
    if lowered_index < 0:
        return -1, -1
    return lowered_index, lowered_index + len(needle)


def _expand_to_word(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen [start, end) to the whole word so the inflected surface is reported."""
    while start > 0 and re.match(r"\w", text[start - 1], re.UNICODE):
        start -= 1
    while end < len(text) and re.match(r"\w", text[end], re.UNICODE):
        end += 1
    return start, end


def audit_document(
    document: GoldDocument,
    outbound_text: str,
    fake_values: tuple[str, ...] = (),
) -> list[LeakFinding]:
    masked = _mask_fakes(outbound_text, tuple(fake_values))
    normalized_outbound = normalize(masked)
    folded_outbound = fold_diacritics(masked)
    outbound_tokens = tokens(masked)

    findings: list[LeakFinding] = []
    seen: set[tuple[str, int, int]] = set()
    for entity in document.entities:
        finding = _detect_leak(
            entity_type=entity.type,
            original=entity.text,
            doc_id=document.doc_id,
            outbound_text=masked,
            normalized_outbound=normalized_outbound,
            folded_outbound=folded_outbound,
            outbound_tokens=outbound_tokens,
        )
        if finding is None:
            continue
        # One surviving surface == one leak: repeated gold mentions of the same value
        # (comparycja + signature) must not multiply the count.
        key = (finding.type, finding.start, finding.end)
        if key in seen:
            continue
        seen.add(key)
        findings.append(finding)
    return findings


def _detect_leak(
    *,
    entity_type: str,
    original: str,
    doc_id: str,
    outbound_text: str,
    normalized_outbound: str,
    folded_outbound: str,
    outbound_tokens: list[str],
) -> LeakFinding | None:
    if entity_type in _NUMERIC_ID_TYPES:
        original_digits = _digits_only(original)
        if original_digits and original_digits in _digits_only(outbound_text):
            start, end = _find_case_insensitive(outbound_text, original)
            return LeakFinding(
                doc_id=doc_id,
                type=entity_type,
                original=original,
                form_found=original if start >= 0 else original_digits,
                start=max(start, 0),
                end=end if end >= 0 else 0,
                match_mode="exact_id",
            )
        return None

    if entity_type in _EXACT_STRING_TYPES:
        # E-mail / date: only a full-string survival is a leak (a shared year or a
        # stray digit is not — those collide with the gateway's fakes).
        if normalize(original) in normalized_outbound:
            start, end = _find_case_insensitive(outbound_text, original)
            return LeakFinding(
                doc_id=doc_id,
                type=entity_type,
                original=original,
                form_found=original,
                start=max(start, 0),
                end=end if end >= 0 else 0,
                match_mode="exact",
            )
        return None

    # Free-text (PERSON / LOCATION / ADDRESS): exact, inflected, or diacritic-folded.
    normalized_original = normalize(original)
    is_short = len(normalized_original) < _MIN_STEM_LENGTH

    if normalized_original in normalized_outbound:
        start, end = _find_case_insensitive(outbound_text, original)
        if start >= 0:
            word_start, word_end = _expand_to_word(outbound_text, start, end)
            form_found = outbound_text[word_start:word_end]
            standalone = normalize(form_found) == normalized_original
            if not is_short or standalone:
                return LeakFinding(
                    doc_id=doc_id,
                    type=entity_type,
                    original=original,
                    form_found=form_found,
                    start=word_start,
                    end=word_end,
                    match_mode="exact" if standalone else "stem",
                )

    if is_short:
        return None

    target = max(tokens(original), key=len, default=original)
    if len(normalize(target)) >= _MIN_STEM_LENGTH:
        for candidate in outbound_tokens:
            if shares_stem(candidate, target):
                start, end = _find_case_insensitive(outbound_text, candidate)
                return LeakFinding(
                    doc_id=doc_id,
                    type=entity_type,
                    original=original,
                    form_found=candidate,
                    start=max(start, 0),
                    end=end if end >= 0 else 0,
                    match_mode="stem",
                )

    if fold_diacritics(original) in folded_outbound:
        return LeakFinding(
            doc_id=doc_id,
            type=entity_type,
            original=original,
            form_found=fold_diacritics(original),
            start=0,
            end=0,
            match_mode="diacritic_fold",
        )
    return None


def aggregate_leaks(findings: list[LeakFinding]) -> LeakReport:
    by_type: dict[str, int] = {}
    by_doc: dict[str, int] = {}
    for finding in findings:
        by_type[finding.type] = by_type.get(finding.type, 0) + 1
        by_doc[finding.doc_id] = by_doc.get(finding.doc_id, 0) + 1
    return LeakReport(
        total_leaks=len(findings),
        by_type=by_type,
        by_doc=by_doc,
        findings=findings,
    )
