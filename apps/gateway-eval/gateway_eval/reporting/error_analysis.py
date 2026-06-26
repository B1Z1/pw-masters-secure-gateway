"""Error-analysis report (FR-031/FR-032) — the "edge cases / what to improve" section.

Lists concrete false negatives, false positives, restoration failures, and leaks.
Originals from ``source="real"`` documents are REDACTED (type only); synthetic
originals are shown (they are fake by construction). Written as markdown for the thesis.
"""

from __future__ import annotations

from pathlib import Path

from .result_models import AggregateResult, PerDocumentResult


def write_report(
    aggregate: AggregateResult,
    per_document: list[PerDocumentResult],
    out_dir: Path,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    real_ids = {d.doc_id for d in per_document if d.source == "real"}
    lines: list[str] = [
        "# Error analysis — edge cases and improvement opportunities",
        "",
    ]

    lines += _detection_summary(aggregate)
    lines += _false_negatives(per_document, real_ids)
    lines += _false_positives(per_document, real_ids)
    lines += _restoration_failures(per_document, real_ids)
    lines += _leaks(aggregate, real_ids)

    path = out_dir / "error_analysis.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _redact(doc_id: str, value: str, real_ids: set[str]) -> str:
    return "[REDACTED]" if doc_id in real_ids else value


def _detection_summary(aggregate: AggregateResult) -> list[str]:
    if aggregate.detection_overlap is None:
        return []
    lines = ["## Detection (overlap policy) — per-type misses/spurious", ""]
    for metrics in aggregate.detection_overlap.per_type:
        if metrics.support == 0:
            continue
        lines.append(
            f"- **{metrics.type}**: recall={metrics.recall}, fn={metrics.fn}, "
            f"fp={metrics.fp} (support {metrics.support})"
        )
    if aggregate.detection_overlap.unmapped_labels:
        lines.append("")
        lines.append(
            f"- Unmapped gateway labels (counted as FP): "
            f"{aggregate.detection_overlap.unmapped_labels}"
        )
    lines.append("")
    return lines


def _false_negatives(per_document, real_ids) -> list[str]:
    lines = ["## False negatives (missed PII — the priority failure)", ""]
    found = False
    for document in per_document:
        for item in document.false_negatives:
            found = True
            type_label, _, surface = item.partition(": ")
            shown = _redact(document.doc_id, surface, real_ids)
            lines.append(f"- {document.doc_id} [{type_label}]: {shown}")
    if not found:
        lines.append("- none")
    lines.append("")
    return lines


def _false_positives(per_document, real_ids) -> list[str]:
    lines = ["## False positives (spurious / unmapped detections)", ""]
    found = False
    for document in per_document:
        for item in document.false_positives:
            found = True
            lines.append(f"- {document.doc_id}: {item}")
    if not found:
        lines.append("- none")
    lines.append("")
    return lines


def _restoration_failures(per_document, real_ids) -> list[str]:
    lines = ["## Restoration failures (not exactly restored)", ""]
    found = False
    for document in per_document:
        for detail in document.restoration:
            if detail.outcome == "exact" and detail.position_correct:
                continue
            found = True
            original = _redact(document.doc_id, detail.original, real_ids)
            restored = _redact(
                document.doc_id, detail.restored_surface or "-", real_ids
            )
            lines.append(
                f"- {document.doc_id} [{detail.type}] {detail.outcome}: "
                f"{original} → {restored}"
            )
    if not found:
        lines.append("- none")
    lines.append("")
    return lines


def _leaks(aggregate: AggregateResult, real_ids) -> list[str]:
    lines = ["## PII leaks (must be zero)", ""]
    if aggregate.leak is None or not aggregate.leak.findings:
        lines.append("- none — zero-leak bar met ✅")
        lines.append("")
        return lines
    for finding in aggregate.leak.findings:
        original = _redact(finding.doc_id, finding.original, real_ids)
        form = _redact(finding.doc_id, finding.form_found, real_ids)
        lines.append(
            f"- {finding.doc_id} [{finding.type}] ({finding.match_mode}): "
            f"{original} surfaced as {form}"
        )
    lines.append("")
    return lines
