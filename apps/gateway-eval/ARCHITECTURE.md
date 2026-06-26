# gateway-eval — architecture & agent context

This document gives a future agent (or reader) enough context to work on the evaluation
harness **without reading all the code**. It explains what each part is responsible for,
how data flows, and the invariants that must not be broken. For the *why* behind the
design decisions, see `specs/008-gateway-eval-harness/` (spec.md, plan.md, research.md
D1–D9, data-model.md, contracts/).

## What this app is

`gateway-eval` is a **black-box evaluation harness** (EPIC 8). It drives the **live**
anonymization gateway over its public HTTP API and measures, against an **independent
gold standard**, how well the gateway detects, replaces, and restores PII in Polish
civil-law contracts. It is the evidence base for the thesis evaluation chapter
(`thesis/content/06-testy-ewaluacja`).

It is **not** part of the production gateway and changes **no** gateway behaviour. It is
an isolated Nx Python app (its own `pyproject.toml`/`.venv`) so its eval-only deps
(`scikit-learn`, `matplotlib`, `seaborn`, `pandas`) never enter the gateway image.

## The two non-negotiable rules

1. **Anti-circularity (D1).** Ground truth comes **only** from the gold standard. Nothing
   under `scoring/` may import `gateway_api` or use the gateway's detected/replaced
   entities as the *answer key*. (Enforced by `tests/test_no_circular_ground_truth.py`.)
   The gateway's outputs are the *predictions under test*, never the oracle.
2. **Privacy / offline (D6).** Everything runs offline against the Echo provider. The real
   40% of the corpus (`corpus/data/real/`, git-ignored) and any results embedding
   originals are never published; only aggregate metrics + redacted examples reach the
   thesis.

## Two stages

- **Stage 1 (no LLM)** — `POST /v1/detect`, `/v1/pseudonymize`, `/v1/depseudonymize`.
  Produces detection P/R/F1 + confusion matrix, the leak audit, round-trip restoration,
  and wall-clock latency. This is the authoritative source of the correctness metrics.
- **Stage 2 (full flow)** — `POST /v1/chat/completions` with `model="echo/echo"` (the
  deterministic Echo provider — a stub, **not** a real LLM). Confirms the integrated
  pipeline is leak-free and restores, and collects the gateway's `anonymization_meta.timing_ms`.
  CLI flag `--stage 1|2|both`.

## Module map (what each part is responsible for)

```
gateway_eval/
├── config.py                  EvaluationConfig: base_url, corpus paths, out/results dirs,
│                              stage, seed, strict_spans, timeouts, latency buckets.
├── run_evaluation.py          ORCHESTRATOR. health-gate → load corpus → per-doc stage(s)
│                              → score → assemble AggregateResult. Owns exit codes
│                              (0 ok / 1 leak / 2 cannot-run) and the per-doc loop.
├── __main__.py                typer CLI: `evaluate` + `build-corpus`. Prints the summary,
│                              writes results (results_writer) + reports (figures/tables/
│                              error_analysis). `python -m gateway_eval ...`.
│
├── corpus/                    THE ORACLE + corpus construction
│   ├── gold_standard.py       GoldEntity/GoldDocument + JSONL IO + the offset==text
│   │                          invariant (hard error). corpus_stats(), load_corpus().
│   ├── entity_vocabulary.py   10 canonical types + gateway-label alias map
│   │                          (POLISH_ADDRESS→ADDRESS, NRB/IBAN→BANK_ACCOUNT, …);
│   │                          normalize_label() (None = unmapped → counted as FP).
│   ├── synthetic_corpus_builder.py  Seeded build: fills templates/ slots with Faker
│   │                          pl_PL values (checksum-validated via gateway_api.checksums),
│   │                          records EXACT offsets → gold is automatic. Reproducible.
│   ├── real_corpus_loader.py  Loads + validates manually-annotated real docs (source="real").
│   ├── templates/*.txt        Full Polish contracts with {{TYPE:role}} slots.
│   └── data/synthetic/*.jsonl committed corpus ; data/real/ git-ignored (real PII).
│
├── gateway_client/
│   └── evaluation_client.py   Async httpx client + response views (DetectedSpan,
│                              PseudonymizeView, ChatView…). health() never raises
│                              (returns not-ok) so a degraded gateway fails gracefully.
│                              Exposes the gateway's declared fake values (for the leak mask).
│
├── stages/
│   ├── stage1_pseudonymize.py Per doc: detect→pseudonymize→depseudonymize, fresh session
│   │                          deleted after; gathers spans, outbound text, fakes, restored
│   │                          text, wall-clock samples.
│   └── stage2_chat_flow.py    Per doc: chat/completions (echo); gathers declared outbound
│                              content, fakes, restored answer, timing_ms.
│
├── scoring/                   PURE LOGIC — imports NO gateway_api (anti-circularity)
│   ├── span_alignment.py      Greedy 1:1 align predicted↔gold; overlap (primary) + exact.
│   ├── detection_metrics.py   TP/FP/FN → P/R/F1 per type + micro/macro; confusion matrix;
│   │                          unmapped labels → FP (M2); combine_reports() for corpus agg;
│   │                          error_spans() lists concrete FN/FP.
│   ├── leak_audit.py          Scans outbound for ANY surviving original. Type-aware:
│   │                          numeric IDs by digits, email/date by full string, names/
│   │                          places by exact-or-stem (inflected = full leak). MASKS the
│   │                          gateway's declared fakes first (so Faker-pool collisions
│   │                          aren't false leaks) and DEDUPES by position. Pass bar = 0.
│   ├── restoration_metrics.py Per-entity outcome (exact/correct_inflection/fuzzy/
│   │                          base_form_only/missed) + document exact-restore rate.
│   └── surface_matching.py    Polish normalize/diacritic-fold/stem/levenshtein helpers
│                              shared by leak_audit + restoration_metrics.
│
├── latency/
│   └── timing_collector.py    Wall-clock (Stage 1) + timing_ms parse (Stage 2); bucket by
│                              length/entity-count; percentile aggregation.
│
└── reporting/
    ├── result_models.py       ALL result/report pydantic shapes (single source — M1).
    ├── results_writer.py      aggregate.json + per_document.jsonl + CSVs (leaks redacted
    │                          for source="real").
    ├── figures.py             matplotlib/seaborn → 4 figure types (PNG+SVG).
    ├── tables.py              Typst #table snippets for the thesis.
    └── error_analysis.py      error_analysis.md (FN/FP/restoration/leaks); redacts real
                               originals, shows synthetic ones.
```

## Data flow (one document, Stage 1)

```
GoldDocument.text ──HTTP──▶ /v1/detect ──▶ predicted spans ─┐
                  ──HTTP──▶ /v1/pseudonymize ──▶ outbound text + fake values
                  ──HTTP──▶ /v1/depseudonymize ──▶ restored text
                                                            │
gold entities (oracle) ─────────────────────────────────┐  │
                                                         ▼  ▼
   detection_metrics (align gold↔predicted)   leak_audit(gold originals vs outbound,
   restoration_metrics (gold vs restored)        masking declared fakes)
                                                         │
                                              PerDocumentResult ──▶ AggregateResult
```

The harness never trusts the gateway about *what the truth is*; it only consumes the
gateway's text outputs and scores them against gold.

## How to run

```bash
nx run gateway-eval:install            # or: uv sync (needs the gateway-api path dep)
nx run gateway-eval:build-corpus       # offline, seeded synthetic corpus
nx run gateway-eval:evaluate -- --stage both        # vs http://localhost:8000
nx run gateway-eval:test               # unit + in-process e2e (FakeGateway, hermetic)

# direct, reusing a local .venv:
PYTHONPATH=. .venv/bin/python -m gateway_eval evaluate --stage both \
  --base-url http://localhost:8000 --out eval-results/images --results eval-results
```

Stage 2 against the live stack needs the gateway's additive `echo/` provider route
(`model: "echo/echo"`) — rebuild the gateway image after enabling it
(`specs/008-gateway-eval-harness/contracts/gateway-echo-route.md`).

## Tests

`tests/` mirrors the package. Unit tests for span alignment, detection metrics, leak
audit (incl. fake-masking + dedup), restoration, latency, gold validation, synthetic
builder (skipped if gateway_api/presidio unavailable). `test_end_to_end.py` drives the
harness against an in-process **FakeGateway** (built from gold, scored independently) so
CI is hermetic — no network, Redis, or spaCy. `test_no_circular_ground_truth.py` is the
structural anti-circularity guard.

## Gotchas a future agent should know

- The committed `corpus/data/synthetic/synthetic_corpus.jsonl` is **JSONL** (one compact
  object per line). An IDE "format on save" can pretty-print it and break the format —
  regenerate with `build-corpus` if that happens.
- `scoring/` must stay free of `gateway_api` imports (guard test). The only sanctioned
  gateway-output use is `leak_audit` masking the *declared fakes* — never as the oracle.
- The synthetic corpus alone meets the ≥50-doc / ≥500-instance floor (CI/repro need no
  real data); the real set augments it for the thesis and stays local-only.
- `leniency` of the gateway's PhoneRecognizer matters: the harness surfaced that the
  default (VALID) leaked possible-but-unassigned numbers (fixed on the gateway side).
```
