"""T015 — span alignment: overlap vs strict-exact, multi-occurrence, greedy 1:1."""

from __future__ import annotations

from gateway_eval.scoring.span_alignment import Span, align


def _kinds(pairs):
    return sorted(pair.match_kind for pair in pairs)


def test_exact_match_under_both_policies():
    gold = [Span("PERSON", 0, 5, "Jan K")]
    pred = [Span("PERSON", 0, 5, "Jan K")]
    assert _kinds(align(gold, pred, "overlap")) == ["exact"]
    assert _kinds(align(gold, pred, "exact")) == ["exact"]


def test_partial_overlap_matches_overlap_but_not_exact():
    gold = [Span("PERSON", 0, 10, "Jan Kowal.")]
    pred = [Span("PERSON", 3, 8, "Kowal")]
    assert _kinds(align(gold, pred, "overlap")) == ["overlap"]
    # strict: no exact-boundary match → one FN + one FP
    assert _kinds(align(gold, pred, "exact")) == ["fn", "fp"]


def test_different_type_same_span_never_matches():
    gold = [Span("PERSON", 0, 5, "00000")]
    pred = [Span("PESEL", 0, 5, "00000")]
    assert _kinds(align(gold, pred, "overlap")) == ["fn", "fp"]


def test_greedy_one_to_one_prevents_double_match():
    # One prediction overlaps two gold spans → only one match, one FN.
    gold = [Span("PERSON", 0, 4, "Jan "), Span("PERSON", 4, 9, "Kowal")]
    pred = [Span("PERSON", 0, 9, "Jan Kowal")]
    kinds = _kinds(align(gold, pred, "overlap"))
    assert kinds.count("overlap") == 1
    assert kinds.count("fn") == 1


def test_multi_occurrence_two_to_two():
    gold = [Span("PERSON", 0, 3, "Jan"), Span("PERSON", 10, 14, "Anna")]
    pred = [Span("PERSON", 0, 3, "Jan"), Span("PERSON", 10, 14, "Anna")]
    assert _kinds(align(gold, pred, "overlap")) == ["exact", "exact"]
