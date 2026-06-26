"""Thesis-ready figures (FR-030) — PNG + SVG into the configurable out dir.

Confusion-matrix heatmap, per-type P/R/F1 bars (recall emphasized), latency
distributions, and the restoration-outcome breakdown. All carry only aggregate
metrics — no originals (FR-032). Uses a non-interactive backend so it runs headless.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402

from .result_models import AggregateResult  # noqa: E402


def render_all(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if aggregate.detection_overlap is not None:
        written += _confusion_matrix(aggregate, out_dir)
        written += _prf1_by_type(aggregate, out_dir)
    if aggregate.restoration is not None:
        written += _restoration_outcomes(aggregate, out_dir)
    if aggregate.latency is not None and aggregate.latency.by_channel:
        written += _latency_distribution(aggregate, out_dir)
    return written


def _save(figure, out_dir: Path, stem: str) -> list[Path]:
    paths = [out_dir / f"{stem}.png", out_dir / f"{stem}.svg"]
    for path in paths:
        figure.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(figure)
    return paths


def _confusion_matrix(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    matrix = aggregate.detection_overlap.confusion_matrix
    figure, axis = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        matrix.matrix,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=matrix.labels,
        yticklabels=matrix.labels,
        ax=axis,
    )
    axis.set_xlabel("predicted")
    axis.set_ylabel("gold")
    axis.set_title("Detection confusion matrix (type + overlap)")
    return _save(figure, out_dir, "confusion_matrix")


def _prf1_by_type(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    per_type = [m for m in aggregate.detection_overlap.per_type if m.support > 0]
    types = [m.type for m in per_type]
    figure, axis = plt.subplots(figsize=(11, 6))
    positions = range(len(types))
    width = 0.27
    # Recall first / leftmost and bold-coloured (Constitution II / FR-018).
    axis.bar(
        [p - width for p in positions],
        [m.recall for m in per_type],
        width,
        label="recall",
        color="#1f77b4",
    )
    axis.bar(
        list(positions),
        [m.precision for m in per_type],
        width,
        label="precision",
        color="#aec7e8",
    )
    axis.bar(
        [p + width for p in positions],
        [m.f1 for m in per_type],
        width,
        label="F1",
        color="#c7c7c7",
    )
    axis.set_xticks(list(positions))
    axis.set_xticklabels(types, rotation=45, ha="right")
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("score")
    axis.set_title(
        "Detection precision / recall / F1 by entity type (recall = priority)"
    )
    axis.legend()
    return _save(figure, out_dir, "prf1_by_type")


def _restoration_outcomes(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    order = [
        "exact",
        "correct_inflection",
        "fuzzy_recovered",
        "base_form_only",
        "missed",
    ]
    by_type = aggregate.restoration.by_type
    types = sorted(by_type)
    figure, axis = plt.subplots(figsize=(11, 6))
    positions = list(range(len(types)))
    bottom = [0.0] * len(types)
    palette = sns.color_palette("viridis", len(order))
    for outcome, colour in zip(order, palette, strict=False):
        values = [by_type[t].get(outcome, 0) for t in types]
        axis.bar(positions, values, bottom=bottom, label=outcome, color=colour)
        bottom = [b + v for b, v in zip(bottom, values, strict=False)]
    axis.set_xticks(positions)
    axis.set_xticklabels(types, rotation=45, ha="right")
    axis.set_ylabel("entities")
    axis.set_title(
        f"Restoration outcomes by type "
        f"(doc exact-restore rate = {aggregate.restoration.doc_exact_restore_rate})"
    )
    axis.legend()
    return _save(figure, out_dir, "restoration_outcomes")


def _latency_distribution(aggregate: AggregateResult, out_dir: Path) -> list[Path]:
    channels = sorted(aggregate.latency.by_channel)
    p50 = [aggregate.latency.by_channel[c].p50 for c in channels]
    p90 = [aggregate.latency.by_channel[c].p90 for c in channels]
    figure, axis = plt.subplots(figsize=(11, 6))
    positions = range(len(channels))
    width = 0.4
    axis.bar([p - width / 2 for p in positions], p50, width, label="p50")
    axis.bar([p + width / 2 for p in positions], p90, width, label="p90")
    axis.set_xticks(list(positions))
    axis.set_xticklabels(channels, rotation=45, ha="right")
    axis.set_ylabel("latency (ms)")
    axis.set_title("Latency by channel (p50 / p90)")
    axis.legend()
    return _save(figure, out_dir, "latency_distribution")
