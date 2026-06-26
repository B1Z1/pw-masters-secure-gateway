"""T016 — detection metrics: P/R/F1, micro/macro, confusion matrix, unmapped→FP."""

from __future__ import annotations

from gateway_eval.corpus.gold_standard import GoldEntity
from gateway_eval.gateway_client.evaluation_client import DetectedSpan
from gateway_eval.scoring.detection_metrics import build_detection_report


def _gold(type_, start, end, text):
    return GoldEntity(type=type_, start=start, end=end, text=text)


def _pred(entity_type, start, end, text=""):
    return DetectedSpan(entity_type=entity_type, start=start, end=end, score=0.9, text=text)


def _metrics(report, entity_type):
    return next(m for m in report.per_type if m.type == entity_type)


def test_perfect_detection_recall_and_precision_one():
    gold = [_gold("PERSON", 0, 3, "Jan"), _gold("PESEL", 10, 21, "90010112345")]
    pred = [_pred("PERSON", 0, 3), _pred("PESEL", 10, 21)]
    report = build_detection_report(gold, pred, "overlap")
    assert report.micro.recall == 1.0
    assert report.micro.precision == 1.0
    assert _metrics(report, "PERSON").tp == 1


def test_label_normalization_polish_address_to_address():
    gold = [_gold("ADDRESS", 0, 5, "ul. X")]
    pred = [_pred("POLISH_ADDRESS", 0, 5)]
    report = build_detection_report(gold, pred, "overlap")
    assert _metrics(report, "ADDRESS").tp == 1
    assert _metrics(report, "ADDRESS").recall == 1.0


def test_unmapped_label_counts_as_false_positive():
    gold = [_gold("PERSON", 0, 3, "Jan")]
    pred = [_pred("PERSON", 0, 3), _pred("ORGANIZATION", 5, 9)]
    report = build_detection_report(gold, pred, "overlap")
    assert report.unmapped_labels == {"ORGANIZATION": 1}
    # tp=1, fp=1 (the unmapped org) → precision 0.5
    assert report.micro.precision == 0.5
    assert report.micro.recall == 1.0


def test_missed_gold_is_false_negative_and_miss_cell():
    gold = [_gold("PERSON", 0, 3, "Jan"), _gold("PESEL", 10, 21, "90010112345")]
    pred = [_pred("PERSON", 0, 3)]  # PESEL missed
    report = build_detection_report(gold, pred, "overlap")
    assert _metrics(report, "PESEL").fn == 1
    assert _metrics(report, "PESEL").recall == 0.0
    labels = report.confusion_matrix.labels
    pesel_row = labels.index("PESEL")
    miss_col = labels.index("MISS")
    assert report.confusion_matrix.matrix[pesel_row][miss_col] == 1


def test_macro_averages_over_supported_types():
    gold = [_gold("PERSON", 0, 3, "Jan"), _gold("PESEL", 10, 21, "90010112345")]
    pred = [_pred("PERSON", 0, 3)]  # PERSON recall 1, PESEL recall 0
    report = build_detection_report(gold, pred, "overlap")
    assert report.macro.recall == 0.5
