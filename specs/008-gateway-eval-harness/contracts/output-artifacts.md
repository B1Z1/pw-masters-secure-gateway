# Contract: Output artifacts

A run produces machine-readable results, figures, Typst tables, and an error-analysis report. Two
destinations with different sensitivity (D6):

- **Publishable** → `--out` (default `thesis/images/`): figures + Typst tables + aggregate JSON. Contains
  **only** aggregate metrics and redacted/pseudonymized examples — never real originals.
- **Sensitive** → `--results` (default sibling `eval-results/`): per-document JSON that may embed
  originals. For runs including `source="real"` docs this directory is treated as sensitive (kept with the
  git-ignored real data, never published).

## Machine-readable (FR-029)

| File | Content |
|------|---------|
| `aggregate.json` | `AggregateResult` (data-model §7) — the publishable, originals-free summary. |
| `per_document.jsonl` | one `PerDocumentResult` per line (sensitive; may embed originals). |
| `detection_per_type.csv` | type, support, TP/FP/FN, precision, recall, f1 (overlap + exact columns). |
| `latency.csv` | channel, bucket, p50/p90/p99/mean/n. |
| `leaks.csv` | doc_id, type, form_found, match_mode (value column **redacted** for `source="real"`). |
| `restoration.csv` | type, outcome counts, doc exact-restore rate. |

## Figures (FR-030) — into `--out`, PNG **and** SVG

| File stem | Figure |
|-----------|--------|
| `confusion_matrix` | heatmap over canonical types + MISS/SPURIOUS (primary/overlap policy). |
| `prf1_by_type` | grouped P/R/F1 bars per entity type, **recall emphasized** (FR-018). |
| `latency_distribution` | per-channel distributions, faceted by length/entity-count bucket. |
| `restoration_outcomes` | stacked bars of the five recovery categories, overall + per type. |

## Typst tables (thesis-ready)

CSV is mirrored as Typst `#table(...)` snippets (`*.typ`) for direct `include` into
`thesis/content/06-testy-ewaluacja`: a per-type detection table (recall-first column order), a latency
summary table, and a restoration-outcome table. No real originals appear.

## Error-analysis report (FR-031) — `error_analysis.md`

Lists concrete failing cases for the thesis "edge cases / what to improve" section:
- **False negatives** — gold entities the gateway missed (type, gold value, surrounding context).
- **False positives** — gateway spans with no gold match (incl. unmapped labels like `ORGANIZATION`).
- **Restoration failures** — originals not recovered (outcome ≠ `exact`), with the recovered surface.
- **Leaks** — every `LeakFinding` (the zero-leak audit detail).

**Redaction rule (D6)**: for `source="real"` documents the report shows the entity **type** and a
**redacted/pseudonymized** stand-in (never the real original); for `source="synthetic"` the synthetic
original may be shown (it is fake by construction). The report is structured so the publishable subset
(synthetic + aggregates) can be lifted into the thesis directly.

## Determinism

Given the same committed corpus + an unchanged gateway, `aggregate.json` metrics are reproducible; the
`RunConfigSnapshot` (seed, base URL, gateway health, corpus hash, span policy, timestamps) is embedded so
any figure/table is traceable to its run (D7).
