"""Round-trip restoration fidelity (FR-022).

For each gold original, classify HOW it was recovered in the de-pseudonymized text:
exact / correct_inflection / fuzzy_recovered / base_form_only / missed, and report a
document-level exact-restoration rate. Structured identifiers admit only exact
recovery (no inflection). Pure logic — scored against gold, never the gateway (D1).
"""

from __future__ import annotations

import re

from ..corpus.entity_vocabulary import is_structured
from ..corpus.gold_standard import GoldDocument
from ..reporting.result_models import RestorationDetail, RestorationReport
from .surface_matching import (
    fold_diacritics,
    levenshtein_ratio,
    normalize,
    shares_stem,
    tokens,
)

_FUZZY_THRESHOLD = 0.8
_DIGITS = re.compile(r"\d+")


def _digits_only(text: str) -> str:
    return "".join(_DIGITS.findall(text))


def _contains_whole(text: str, phrase: str) -> bool:
    """True if ``phrase`` occurs in ``text`` not as a fragment of a longer word
    (so ``Kowalski`` does NOT match inside ``Kowalskiego``)."""
    start = 0
    while True:
        found = text.find(phrase, start)
        if found < 0:
            return False
        before = text[found - 1] if found > 0 else " "
        after_index = found + len(phrase)
        after = text[after_index] if after_index < len(text) else " "
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        start = found + 1


def _is_word_char(character: str) -> bool:
    return bool(re.match(r"\w", character, re.UNICODE))


def classify_one(
    *,
    original: str,
    entity_type: str,
    start: int,
    end: int,
    original_text: str,
    restored_text: str,
) -> tuple[str, str | None, bool]:
    """Return ``(outcome, restored_surface, position_correct)`` for one original."""
    if restored_text[start:end] == original:
        return "exact", original, True
    if _contains_whole(restored_text, original):
        return "exact", original, False

    if is_structured(entity_type):
        original_digits = _digits_only(original)
        if original_digits and original_digits in _digits_only(restored_text):
            return "exact", original, False
        return "missed", None, False

    target = _identifying_token(original)
    candidate = _best_token_candidate(target, restored_text)
    if candidate is None:
        return "missed", None, False

    normalized_candidate = normalize(candidate)
    normalized_target = normalize(target)
    if normalized_candidate == normalized_target:
        return "correct_inflection", candidate, False
    if fold_diacritics(candidate) == fold_diacritics(target):
        return "correct_inflection", candidate, False
    if normalized_target.startswith(normalized_candidate) and len(
        normalized_candidate
    ) < len(normalized_target):
        return "base_form_only", candidate, False
    if shares_stem(candidate, target):
        return "correct_inflection", candidate, False
    return "fuzzy_recovered", candidate, False


def _identifying_token(original: str) -> str:
    parts = tokens(original)
    return max(parts, key=len) if parts else original


def _best_token_candidate(target: str, restored_text: str) -> str | None:
    best: str | None = None
    best_score = 0.0
    for candidate in tokens(restored_text):
        if shares_stem(candidate, target):
            return candidate
        score = levenshtein_ratio(candidate, target)
        if score > best_score:
            best_score, best = score, candidate
    return best if best is not None and best_score >= _FUZZY_THRESHOLD else None


def build_restoration_details(
    document: GoldDocument, restored_text: str
) -> list[RestorationDetail]:
    details: list[RestorationDetail] = []
    for entity in document.entities:
        outcome, restored_surface, position_correct = classify_one(
            original=entity.text,
            entity_type=entity.type,
            start=entity.start,
            end=entity.end,
            original_text=document.text,
            restored_text=restored_text,
        )
        details.append(
            RestorationDetail(
                doc_id=document.doc_id,
                type=entity.type,
                original=entity.text,
                outcome=outcome,
                restored_surface=restored_surface,
                position_correct=position_correct,
            )
        )
    return details


def aggregate_restoration(
    details_by_doc: dict[str, list[RestorationDetail]],
) -> RestorationReport:
    by_outcome: dict[str, int] = {}
    by_type: dict[str, dict[str, int]] = {}
    exact_documents = 0
    total_documents = 0
    for details in details_by_doc.values():
        if not details:
            continue
        total_documents += 1
        document_all_exact = True
        for detail in details:
            by_outcome[detail.outcome] = by_outcome.get(detail.outcome, 0) + 1
            type_counts = by_type.setdefault(detail.type, {})
            type_counts[detail.outcome] = type_counts.get(detail.outcome, 0) + 1
            if not (detail.outcome == "exact" and detail.position_correct):
                document_all_exact = False
        if document_all_exact:
            exact_documents += 1
    rate = exact_documents / total_documents if total_documents else 0.0
    return RestorationReport(
        by_outcome=by_outcome,
        by_type=by_type,
        doc_exact_restore_rate=round(rate, 4),
    )
