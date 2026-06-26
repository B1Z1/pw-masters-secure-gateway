"""Thesis-ready Typst tables (FR-029/FR-030).

Emits ``#table(...)`` snippets for direct ``#include`` into
``thesis/content/06-testy-ewaluacja``. Recall-first column order for the detection
table (Constitution II). Only aggregate metrics — no originals (FR-032).
"""

from __future__ import annotations

from pathlib import Path

from .result_models import AggregateResult


def write_typst_tables(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if aggregate.detection_overlap is not None:
        written.append(_detection_table(aggregate, out_dir))
    if aggregate.restoration is not None:
        written.append(_restoration_table(aggregate, out_dir))
    if aggregate.latency is not None and aggregate.latency.by_channel:
        written.append(_latency_table(aggregate, out_dir))
    return written


def _cell(value) -> str:
    return f"[{value}]"


def _detection_table(aggregate: AggregateResult, out_dir: Path) -> Path:
    exact_by_type = {
        m.type: m
        for m in (
            aggregate.detection_exact.per_type if aggregate.detection_exact else []
        )
    }
    rows = [
        "#table(",
        "  columns: 6,",
        "  align: (left, right, right, right, right, right),",
        "  table.header[Typ][Recall][Precision][F1][Recall (exact)][Wsparcie],",
    ]
    for metrics in aggregate.detection_overlap.per_type:
        if metrics.support == 0:
            continue
        strict = exact_by_type.get(metrics.type)
        rows.append(
            "  "
            + _cell(metrics.type)
            + _cell(metrics.recall)
            + _cell(metrics.precision)
            + _cell(metrics.f1)
            + _cell(strict.recall if strict else "-")
            + _cell(metrics.support)
            + ","
        )
    micro = aggregate.detection_overlap.micro
    rows.append(
        "  "
        + _cell("micro")
        + _cell(micro.recall)
        + _cell(micro.precision)
        + _cell(micro.f1)
        + _cell("")
        + _cell(micro.support)
        + ","
    )
    rows.append(")")
    path = out_dir / "detection_by_type.typ"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _restoration_table(aggregate: AggregateResult, out_dir: Path) -> Path:
    order = [
        "exact",
        "correct_inflection",
        "fuzzy_recovered",
        "base_form_only",
        "missed",
    ]
    by_outcome = aggregate.restoration.by_outcome
    rows = ["#table(", "  columns: 2,", "  table.header[Wynik odtworzenia][Liczba],"]
    for outcome in order:
        rows.append("  " + _cell(outcome) + _cell(by_outcome.get(outcome, 0)) + ",")
    rows.append(
        "  "
        + _cell("doc_exact_restore_rate")
        + _cell(aggregate.restoration.doc_exact_restore_rate)
        + ","
    )
    rows.append(")")
    path = out_dir / "restoration_outcomes.typ"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _latency_table(aggregate: AggregateResult, out_dir: Path) -> Path:
    rows = [
        "#table(",
        "  columns: 5,",
        "  table.header[Kanał][p50 (ms)][p90 (ms)][p99 (ms)][n],",
    ]
    for channel in sorted(aggregate.latency.by_channel):
        stats = aggregate.latency.by_channel[channel]
        rows.append(
            "  "
            + _cell(channel)
            + _cell(stats.p50)
            + _cell(stats.p90)
            + _cell(stats.p99)
            + _cell(stats.n)
            + ","
        )
    rows.append(")")
    path = out_dir / "latency_summary.typ"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path
