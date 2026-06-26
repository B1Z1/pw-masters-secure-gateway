"""Detection P/R/F1 + confusion matrix from gold↔predicted alignment (FR-016/D3/D8).

Ground truth is the gold standard only (D1). Gateway labels are normalized to the
canonical vocabulary; an unmapped predicted label is surfaced in ``unmapped_labels``
**and** counted as a false positive (analysis M2), so precision stays conservative.
Recall is the priority metric (Constitution II) — it is what the report foregrounds.
"""

from __future__ import annotations

from typing import Protocol

from ..corpus.entity_vocabulary import CANONICAL_TYPES, normalize_label
from ..corpus.gold_standard import GoldEntity
from ..reporting.result_models import (
    ConfusionMatrix,
    DetectionReport,
    SpanPolicy,
    TypeMetrics,
)
from .span_alignment import Span, align, positional_pairs

_MISS = "MISS"
_SPURIOUS = "SPURIOUS"


class _PredictedSpan(Protocol):
    entity_type: str
    start: int
    end: int
    text: str


def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def build_detection_report(
    gold: list[GoldEntity],
    predicted: list[_PredictedSpan],
    policy: SpanPolicy,
) -> DetectionReport:
    gold_spans = [Span(g.type, g.start, g.end, g.text) for g in gold]

    mapped_predicted: list[Span] = []
    unmapped_labels: dict[str, int] = {}
    for span in predicted:
        canonical = normalize_label(span.entity_type)
        if canonical is None:
            unmapped_labels[span.entity_type] = (
                unmapped_labels.get(span.entity_type, 0) + 1
            )
            continue
        mapped_predicted.append(Span(canonical, span.start, span.end, span.text))
    unmapped_total = sum(unmapped_labels.values())

    pairs = align(gold_spans, mapped_predicted, policy)

    tp_by_type: dict[str, int] = {}
    fn_by_type: dict[str, int] = {}
    fp_by_type: dict[str, int] = {}
    support_by_type: dict[str, int] = {}
    for gold_span in gold_spans:
        support_by_type[gold_span.type] = support_by_type.get(gold_span.type, 0) + 1
    for pair in pairs:
        if pair.match_kind in ("exact", "overlap") and pair.gold is not None:
            tp_by_type[pair.gold.type] = tp_by_type.get(pair.gold.type, 0) + 1
        elif pair.match_kind == "fn" and pair.gold is not None:
            fn_by_type[pair.gold.type] = fn_by_type.get(pair.gold.type, 0) + 1
        elif pair.match_kind == "fp" and pair.predicted is not None:
            fp_by_type[pair.predicted.type] = fp_by_type.get(pair.predicted.type, 0) + 1

    per_type: list[TypeMetrics] = []
    for entity_type in CANONICAL_TYPES:
        tp = tp_by_type.get(entity_type, 0)
        fp = fp_by_type.get(entity_type, 0)
        fn = fn_by_type.get(entity_type, 0)
        precision, recall, f1 = _prf1(tp, fp, fn)
        per_type.append(
            TypeMetrics(
                type=entity_type,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=precision,
                recall=recall,
                f1=f1,
                support=support_by_type.get(entity_type, 0),
            )
        )

    micro = _micro(tp_by_type, fp_by_type, fn_by_type, unmapped_total)
    macro = _macro(per_type)
    matrix = _confusion_matrix(pairs, unmapped_total)

    return DetectionReport(
        policy=policy,
        per_type=per_type,
        micro=micro,
        macro=macro,
        confusion_matrix=matrix,
        unmapped_labels=unmapped_labels,
    )


def error_spans(
    gold: list[GoldEntity],
    predicted: list[_PredictedSpan],
    policy: SpanPolicy,
) -> tuple[list[str], list[str]]:
    """Concrete false negatives (missed gold) and false positives (spurious preds) for
    the error-analysis report. Unmapped predicted labels are listed as FPs."""
    gold_spans = [Span(g.type, g.start, g.end, g.text) for g in gold]
    mapped: list[Span] = []
    unmapped: list[str] = []
    for span in predicted:
        canonical = normalize_label(span.entity_type)
        if canonical is None:
            unmapped.append(f"{span.entity_type}@{span.start}")
        else:
            mapped.append(Span(canonical, span.start, span.end, span.text))
    pairs = align(gold_spans, mapped, policy)
    false_negatives = [
        f"{pair.gold.type}: {pair.gold.text}"
        for pair in pairs
        if pair.match_kind == "fn" and pair.gold is not None
    ]
    false_positives = [
        f"{pair.predicted.type}@{pair.predicted.start}"
        for pair in pairs
        if pair.match_kind == "fp" and pair.predicted is not None
    ]
    false_positives.extend(unmapped)
    return false_negatives, false_positives


def _micro(
    tp_by_type: dict[str, int],
    fp_by_type: dict[str, int],
    fn_by_type: dict[str, int],
    unmapped_total: int,
) -> TypeMetrics:
    tp = sum(tp_by_type.values())
    fp = sum(fp_by_type.values()) + unmapped_total  # M2: unmapped count as FP
    fn = sum(fn_by_type.values())
    precision, recall, f1 = _prf1(tp, fp, fn)
    return TypeMetrics(
        type="__micro__",
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        support=tp + fn,
    )


def _macro(per_type: list[TypeMetrics]) -> TypeMetrics:
    scored = [metrics for metrics in per_type if metrics.support > 0]
    count = len(scored) or 1
    return TypeMetrics(
        type="__macro__",
        precision=round(sum(m.precision for m in scored) / count, 4),
        recall=round(sum(m.recall for m in scored) / count, 4),
        f1=round(sum(m.f1 for m in scored) / count, 4),
        support=sum(m.support for m in scored),
    )


def _confusion_matrix(pairs, unmapped_total: int) -> ConfusionMatrix:
    labels = [*CANONICAL_TYPES, _MISS, _SPURIOUS]
    index = {label: position for position, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]

    # Diagonal: type-constrained matches (the policy TP).
    for pair in pairs:
        if pair.match_kind in ("exact", "overlap") and pair.gold is not None:
            matrix[index[pair.gold.type]][index[pair.gold.type]] += 1

    # Off-diagonal: positionally-overlapping leftovers reveal type confusion.
    unmatched_gold = [p.gold for p in pairs if p.match_kind == "fn" and p.gold]
    unmatched_pred = [
        p.predicted for p in pairs if p.match_kind == "fp" and p.predicted
    ]
    cross = positional_pairs(unmatched_gold, unmatched_pred)
    cross_gold = {gold_index for gold_index, _ in cross}
    cross_pred = {pred_index for _, pred_index in cross}
    for gold_index, pred_index in cross:
        matrix[index[unmatched_gold[gold_index].type]][
            index[unmatched_pred[pred_index].type]
        ] += 1

    # Pure misses and pure spurious detections.
    for gold_index, gold_span in enumerate(unmatched_gold):
        if gold_index not in cross_gold:
            matrix[index[gold_span.type]][index[_MISS]] += 1
    for pred_index, predicted_span in enumerate(unmatched_pred):
        if pred_index not in cross_pred:
            matrix[index[_SPURIOUS]][index[predicted_span.type]] += 1

    # Unmapped predictions are spurious with no canonical column → SPURIOUS/MISS cell.
    if unmapped_total:
        matrix[index[_SPURIOUS]][index[_MISS]] += unmapped_total

    return ConfusionMatrix(labels=labels, matrix=matrix)


def combine_reports(
    reports: list[DetectionReport], policy: SpanPolicy
) -> DetectionReport:
    """Corpus-level report = sum of per-document reports (alignment is per document)."""
    tp_by_type: dict[str, int] = {}
    fp_by_type: dict[str, int] = {}
    fn_by_type: dict[str, int] = {}
    support_by_type: dict[str, int] = {}
    unmapped_labels: dict[str, int] = {}
    labels = [*CANONICAL_TYPES, _MISS, _SPURIOUS]
    matrix = [[0 for _ in labels] for _ in labels]

    for report in reports:
        for metrics in report.per_type:
            tp_by_type[metrics.type] = tp_by_type.get(metrics.type, 0) + metrics.tp
            fp_by_type[metrics.type] = fp_by_type.get(metrics.type, 0) + metrics.fp
            fn_by_type[metrics.type] = fn_by_type.get(metrics.type, 0) + metrics.fn
            support_by_type[metrics.type] = (
                support_by_type.get(metrics.type, 0) + metrics.support
            )
        for label, count in report.unmapped_labels.items():
            unmapped_labels[label] = unmapped_labels.get(label, 0) + count
        for row in range(len(labels)):
            for column in range(len(labels)):
                matrix[row][column] += report.confusion_matrix.matrix[row][column]

    per_type: list[TypeMetrics] = []
    for entity_type in CANONICAL_TYPES:
        tp = tp_by_type.get(entity_type, 0)
        fp = fp_by_type.get(entity_type, 0)
        fn = fn_by_type.get(entity_type, 0)
        precision, recall, f1 = _prf1(tp, fp, fn)
        per_type.append(
            TypeMetrics(
                type=entity_type,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=precision,
                recall=recall,
                f1=f1,
                support=support_by_type.get(entity_type, 0),
            )
        )

    unmapped_total = sum(unmapped_labels.values())
    return DetectionReport(
        policy=policy,
        per_type=per_type,
        micro=_micro(tp_by_type, fp_by_type, fn_by_type, unmapped_total),
        macro=_macro(per_type),
        confusion_matrix=ConfusionMatrix(labels=labels, matrix=matrix),
        unmapped_labels=unmapped_labels,
    )
