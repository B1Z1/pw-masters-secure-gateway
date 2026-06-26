# Contract: `gateway-eval` CLI

Invoked via `python -m gateway_eval <command>` or the Nx targets. Built with `typer` (D9).

## Commands

### `evaluate` (the `nx run gateway-eval:evaluate` target)

Run the evaluation against a live (or in-process) gateway and write all artifacts.

| Flag | Default | Meaning |
|------|---------|---------|
| `--base-url URL` | `http://localhost:8000` | Live gateway base URL. |
| `--corpus PATH` | committed synthetic dir (+ `data/real/` if present) | Corpus to evaluate. |
| `--out DIR` | `thesis/images/` | Figures + Typst tables (publishable). |
| `--results DIR` | `<out>/../eval-results/` | Machine-readable per-doc + aggregate JSON/CSV. |
| `--stage {1,2,both}` | `both` | Which stage(s) to run. |
| `--provider NAME` | `echo` | Stage 2 provider (maps to `model="echo/echo"`). |
| `--strict-spans` | off | Make exact-span the headline metric (overlap still reported). |
| `--timeout SECONDS` | `30` | Per-request timeout. |

**Flow**: `GET /health` gate → load+validate corpus → per document {fresh `session_id` → run selected
stage(s) → `DELETE` session} → score → write results, figures, tables, error-analysis.

### `build-corpus` (the `nx run gateway-eval:build-corpus` target)

(Re)generate the synthetic corpus deterministically. **Offline, no gateway needed.**

| Flag | Default | Meaning |
|------|---------|---------|
| `--seed INT` | `42` | Faker + selection seed (D7). |
| `--corpus-out PATH` | `gateway_eval/corpus/data/synthetic/` | Where the gold JSONL is written. (Distinct flag name from `evaluate --out` to avoid the dual meaning.) |
| `--count INT` | enough for the synthetic set to **independently** meet ≥ 50 docs / ≥ 500 instances | Documents to generate. |

Same `--seed` ⇒ byte-identical documents + gold standard. The committed synthetic corpus alone satisfies
the ≥ 50-doc / ≥ 500-instance floor (so CI and reproducibility runs need no real data); the real 40% is
added locally to form the thesis blend.

## Exit codes

| Code | Condition |
|------|-----------|
| `0` | Run completed; **and for the leak audit, zero leaks** (the pass bar). |
| `1` | Run completed but the **leak audit failed** (≥ 1 leak) — non-zero so CI/thesis runs surface it. |
| `2` | Could not run: gateway `degraded`/unreachable, or corpus failed validation. |
| `3` | Usage error (bad flags). |

A completed run **always** writes the aggregate report even on exit `1` (the leak findings are the point).

## stdout / stderr

- stdout: a concise human summary (corpus stats, micro/macro P/R/F1, recall headline per type, leak
  count + pass/fail, doc exact-restore rate, where artifacts were written).
- stderr: warnings (unmapped gateway labels, per-document errors, corpus-target shortfalls).
- **Never** prints original PII for `source="real"` documents.
