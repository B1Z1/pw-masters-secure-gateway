"""Align predicted spans to gold spans (research D3).

Two policies, both reported: PRIMARY = same entity type + character-span overlap
("was the PII masked?"); STRICT = same type + exact ``(start, end)``. Assignment is
greedy one-to-one per type, ordered by descending overlap, so one prediction cannot
satisfy two gold spans (and vice versa). ``AlignedPair`` is the only scoring type
defined outside ``result_models`` — it is internal to alignment (data-model §5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SpanPolicy = Literal["overlap", "exact"]
MatchKind = Literal["exact", "overlap", "fp", "fn"]


@dataclass(frozen=True)
class Span:
    """A typed character span — used for both gold and (normalized) predicted spans."""

    type: str
    start: int
    end: int
    text: str = ""


@dataclass(frozen=True)
class AlignedPair:
    gold: Span | None
    predicted: Span | None
    match_kind: MatchKind


def _overlap_length(left: Span, right: Span) -> int:
    return max(0, min(left.end, right.end) - max(left.start, right.start))


def _is_match(gold: Span, predicted: Span, policy: SpanPolicy) -> bool:
    if gold.type != predicted.type:
        return False
    if policy == "exact":
        return gold.start == predicted.start and gold.end == predicted.end
    return _overlap_length(gold, predicted) > 0


def align(
    gold_spans: list[Span], predicted_spans: list[Span], policy: SpanPolicy
) -> list[AlignedPair]:
    """Greedy one-to-one alignment per entity type.

    Returns one ``AlignedPair`` per matched gold↔predicted pair (``match_kind`` =
    ``exact``/``overlap``), one per unmatched gold (``fn``) and one per unmatched
    prediction (``fp``).
    """
    candidate_pairs: list[tuple[int, int, int]] = []  # (overlap, gold_idx, pred_idx)
    for gold_index, gold in enumerate(gold_spans):
        for predicted_index, predicted in enumerate(predicted_spans):
            if _is_match(gold, predicted, policy):
                candidate_pairs.append(
                    (_overlap_length(gold, predicted), gold_index, predicted_index)
                )

    # Highest overlap first; exact policy ties resolve deterministically by index.
    candidate_pairs.sort(key=lambda triple: (-triple[0], triple[1], triple[2]))

    matched_gold: set[int] = set()
    matched_predicted: set[int] = set()
    pairs: list[AlignedPair] = []
    for _, gold_index, predicted_index in candidate_pairs:
        if gold_index in matched_gold or predicted_index in matched_predicted:
            continue
        matched_gold.add(gold_index)
        matched_predicted.add(predicted_index)
        gold = gold_spans[gold_index]
        predicted = predicted_spans[predicted_index]
        kind: MatchKind = (
            "exact"
            if gold.start == predicted.start and gold.end == predicted.end
            else "overlap"
        )
        pairs.append(AlignedPair(gold=gold, predicted=predicted, match_kind=kind))

    for gold_index, gold in enumerate(gold_spans):
        if gold_index not in matched_gold:
            pairs.append(AlignedPair(gold=gold, predicted=None, match_kind="fn"))
    for predicted_index, predicted in enumerate(predicted_spans):
        if predicted_index not in matched_predicted:
            pairs.append(AlignedPair(gold=None, predicted=predicted, match_kind="fp"))
    return pairs


def positional_pairs(
    gold_spans: list[Span], predicted_spans: list[Span]
) -> list[tuple[int, int]]:
    """Greedy overlap match IGNORING type — used only to fill the confusion matrix's
    off-diagonal (type-confusion) cells. Returns ``(gold_index, predicted_index)``."""
    candidate_pairs: list[tuple[int, int, int]] = []
    for gold_index, gold in enumerate(gold_spans):
        for predicted_index, predicted in enumerate(predicted_spans):
            overlap = _overlap_length(gold, predicted)
            if overlap > 0:
                candidate_pairs.append((overlap, gold_index, predicted_index))
    candidate_pairs.sort(key=lambda triple: (-triple[0], triple[1], triple[2]))
    matched_gold: set[int] = set()
    matched_predicted: set[int] = set()
    result: list[tuple[int, int]] = []
    for _, gold_index, predicted_index in candidate_pairs:
        if gold_index in matched_gold or predicted_index in matched_predicted:
            continue
        matched_gold.add(gold_index)
        matched_predicted.add(predicted_index)
        result.append((gold_index, predicted_index))
    return result
