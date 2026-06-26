# Implementation Plan: EPIC 8 (partial) — Gateway PII Evaluation Harness

**Branch**: `008-gateway-eval-harness` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-gateway-eval-harness/spec.md`

## Summary

Build `apps/gateway-eval` (package `gateway_eval`) — a **standalone, black-box** evaluation harness that
drives the **live** gateway over its public HTTP API and measures, against an **independent gold
standard**, how well it detects, replaces, and restores Polish-contract PII. It is the executable
evidence for the thesis evaluation chapter (`thesis/content/06-testy-ewaluacja`).

The harness is a **separate Nx Python app**, isolated from the production gateway image so its eval-only
dependencies (`scikit-learn`, `matplotlib`, `seaborn`, `pandas`, `typer`) never enter the gateway. It
**reuses** two gateway-api modules **for corpus construction only** — `FakeDataGenerator` (realistic PII
injection) and `pii_detection.checksums` (checksum-valid identifiers) — and **never** imports gateway
internals for scoring: scoring runs strictly against the gold standard and the gateway's HTTP responses
(**D1 — ground-truth independence**).

Two stages, selected by `--stage 1|2|both`:
- **Stage 1 (no LLM)** — per document call `POST /v1/detect`, `POST /v1/pseudonymize`,
  `POST /v1/depseudonymize`: detection P/R/F1 + confusion matrix, the inflection-aware PII-leak audit
  (zero-leak bar), round-trip restoration fidelity, and wall-clock latency per endpoint.
- **Stage 2 (full flow)** — per document call `POST /v1/chat/completions` routed to the deterministic
  **Echo** provider: confirm the gateway's declared outbound content is leak-free, the de-pseudonymized
  answer restores, and collect the gateway-reported `anonymization_meta.timing_ms` breakdown.

**One additive gateway-side enablement** (clarified with the user, 2026-06-25): the production router gets
an **opt-in `echo/` provider prefix** wired from the existing `EchoProvider`, so the live docker stack
accepts `--model echo/echo` and the harness can stay pure-HTTP. This is sanctioned by **Constitution IV**
(adding a provider via the adapter pattern, no pipeline change) and alters **no existing behaviour** — see
Constitution Check + Complexity Tracking.

Outputs (default into `thesis/images/`): machine-readable per-document + aggregate JSON/CSV, thesis-ready
figures (confusion-matrix heatmap, per-type P/R/F1 bars, latency distributions, restoration breakdown),
Typst tables, and an error-analysis report. The real 40% of the corpus and any gold standard containing
real originals are **git-ignored and never published** (**D6 — RODO regime**).

Decisions are fixed in [research.md](./research.md) (D1–D9); schemas/result shapes in
[data-model.md](./data-model.md); consumed endpoints + CLI + output-file contracts in
[contracts/](./contracts/); the offline run/validation guide in [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12 (matches gateway-api; `requires-python = ">=3.12,<4"`).

**Primary Dependencies** (eval app only, isolated from the gateway image):
- `httpx` — async client against the live gateway HTTP API.
- `scikit-learn` — `precision/recall/f1` and `confusion_matrix`.
- `matplotlib` + `seaborn` — figures (PNG/SVG).
- `pandas` — tabular aggregation + CSV.
- `pydantic` — config + result models.
- `typer` — CLI (`--stage`, `--base-url`, `--corpus`, `--out`, `--seed`, `--strict-spans`,
  `--provider`). Chosen over argparse for typed sub-options and enum flags (D9).
- **Path dependency on `gateway-api`** (`tool.uv.sources` / editable) — used **only** by the corpus
  builder for `gateway_api.pseudonym_generation.FakeDataGenerator` and
  `gateway_api.pii_detection.checksums` (`pesel_is_valid`, `nip_is_valid`, `regon9_is_valid`,
  `regon14_is_valid`, `nrb_is_valid`). NOT imported anywhere in `scoring/`.

**Storage**: Files only — the corpus is gold-standard JSONL on disk (synthetic committed under
`gateway_eval/corpus/data/`; real under `gateway_eval/corpus/data/real/`, git-ignored). Results/figures
are written to a configurable output dir (default `thesis/images/`). The harness keeps **no** database;
the gateway's Redis is touched only indirectly (a fresh session per document, `DELETE`d afterwards).

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), reusing the gateway-api conftest
pattern. Unit tests for span alignment, leak normalization, restoration classification, checksum-valid
injection, and gold-offset validation. One small **in-process** end-to-end run (Stage 1 + Stage 2) drives
the gateway ASGI app via `httpx.ASGITransport` over `fakeredis` + the Echo dependency-override — no
network, no real keys, no running container — to prove the harness produces a complete report. Run via
`nx run gateway-eval:test`.

**Target Platform**: Local developer machine / Linux. The real evaluation run targets the live stack
(`docker compose up`, default `http://localhost:8000`); CI runs the in-process ASGI variant.

**Project Type**: Offline research CLI tool (batch), part of the Nx monorepo, sibling to `apps/gateway-api`.

**Performance Goals**: None as an SLA. Latency is **measured and reported** (Stage 1 wall-clock per
endpoint; Stage 2 gateway `timing_ms`), bucketed by document length and entity count — it is a thesis
result, not a budget.

**Constraints**: Fully **offline** — no contract text leaves the machine (Echo provider, no external
egress) — Constitution I/VIII are the things under test. Ground truth is the gold standard **only**, never
the gateway's output (anti-circularity). Real corpus + any gold with real originals are git-ignored and
never published; only aggregate metrics + redacted/pseudonymized examples reach the thesis. Synchronous
only (Constitution V) — no streaming endpoints used. No auth (prototype). Synthetic corpus is seeded and
reproducible; the synthetic gold standard is versioned.

**Scale/Scope**: Master's-thesis prototype — the **committed synthetic set alone** meets the ≥ 50-document /
≥ 500-instance floor with all 10 canonical types (so CI/reproducibility need no real data); the ~60/40
synthetic/real blend is the thesis corpus, formed by adding the manually-annotated real portion.
Tens-to-low-hundreds of documents per run; no concurrency requirement.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy by Design | PASS (under test) | The harness is the **executable proof** of Principle I: its leak audit (Stage 1 on `pseudonymized_text`; Stage 2 on `input_anonymization.pseudonymized_content`) asserts that **no original PII** — including inflected/partial forms — reaches the provider boundary, with a **zero-leak** pass bar. It adds no pipeline path and sends no originals onward (Echo is offline). |
| II. Recall over Precision | PASS | Recall is the **headline** detection metric in every table/figure (FR-018); precision/F1 reported alongside. The error-analysis foregrounds false negatives (missed PII). |
| III. Reversibility within Session | PASS | Round-trip is measured **through the public API only**; the harness never reads or asserts on encrypted mappings as ground truth. A fresh `session_id` per document + `DELETE /v1/sessions/{id}` afterwards keeps Redis clean and TTL semantics intact. |
| IV. Provider Agnosticism | PASS (basis for the echo route) | The **only** gateway-side change is an **additive** `echo/` prefix factory in `get_llm_provider`, which is exactly what Principle IV sanctions ("adding a new provider MUST NOT require modifying the pipeline"). Existing prefixes (`gpt-`/`claude-`/`ollama/`) and the pipeline are untouched; the harness selects Echo per request via the `model` field, not by inspecting providers. |
| V. Synchronous Only | PASS | The harness calls only synchronous endpoints; no streaming. Each chat answer is fully received before the harness scores it. |
| VI. Polish First | PASS | The corpus is Polish civil-law contracts; injected PII uses valid Polish formats; the leak/restoration matching handles Polish diacritics and case inflection. |
| VII. Realistic Substitution | PASS | Synthetic PII is generated by the gateway's own `FakeDataGenerator` (`pl_PL`, checksum-valid) — no abstract placeholders — so the corpus mirrors real substitution behaviour. |
| VIII. No PII in Logs | PASS (under test) | The harness asserts gateway logs/responses carry no originals where required, and its **own** outputs split sensitive artifacts (corpus, per-doc results with originals) — git-ignored for the real set — from publishable artifacts (aggregate metrics + redacted examples). |
| IX. Simplicity over Completeness | PASS | A separate app with a thin async client + pure scoring functions; reuses gateway code only for corpus construction. The leak matcher uses a documented normalization + stem rule rather than a full morphological analyzer (limitation documented — D4). |

**Result**: PASS. One deliberate, Constitution-IV-sanctioned additive change to gateway-api (the `echo/`
route) is recorded in **Complexity Tracking** because the spec's prose says "changes no gateway behaviour"
— the change adds a provider without altering any existing behaviour.

## Project Structure

### Documentation (this feature)

```text
specs/008-gateway-eval-harness/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1–D9
├── data-model.md        # Phase 1 — gold-standard schema, result models, scoring entities
├── quickstart.md        # Phase 1 — offline run + validation guide (live stack + in-process)
├── contracts/
│   ├── consumed-endpoints.md   # The gateway HTTP surface the harness calls (request/response it relies on)
│   ├── gateway-echo-route.md   # The additive echo/ provider wiring in gateway-api (the only gateway touch)
│   ├── cli.md                  # gateway-eval CLI contract (flags, exit codes, --stage semantics)
│   ├── gold-standard.md        # The shared gold JSONL schema + validation rules
│   └── output-artifacts.md     # Machine-readable results, figures, Typst tables, error-analysis report
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
apps/gateway-eval/
├── pyproject.toml                 # NEW — uv-managed; eval-only deps + path dep on gateway-api; ruff/pytest config
├── project.json                   # NEW — Nx targets: evaluate, build-corpus, lint, format, test, install/lock/sync
├── README.md                      # NEW — what it is, how to run, RODO/data-handling note
└── gateway_eval/
    ├── __init__.py
    ├── __main__.py                # NEW — `python -m gateway_eval` → CLI
    ├── run_evaluation.py          # NEW — orchestration: load/build corpus → run stage(s) → score → report
    ├── config.py                  # NEW — EvaluationConfig (base_url, corpus path, out dir, seed, strict-spans, provider, timeouts)
    ├── corpus/
    │   ├── __init__.py
    │   ├── gold_standard.py        # NEW — GoldDocument/GoldEntity models + JSONL IO + offset==text validation
    │   ├── synthetic_corpus_builder.py  # NEW — templates + seeded PII injection → gold JSONL with exact offsets
    │   ├── real_corpus_loader.py   # NEW — load + validate manually-annotated real docs (source="real")
    │   ├── entity_vocabulary.py    # NEW — canonical gold types + gateway-label alias map (FR-019)
    │   ├── templates/              # NEW — Polish contract templates (najem, zlecenie, o dzieło, sprzedaż)
    │   └── data/
    │       ├── synthetic/          # NEW — committed synthetic corpus (gold JSONL)
    │       └── real/               # NEW — GIT-IGNORED — real contracts + their gold (never committed)
    ├── gateway_client/
    │   ├── __init__.py
    │   └── evaluation_client.py    # NEW — async httpx client: /health gate + detect/pseudonymize/depseudonymize/chat + sessions; timeout/retry
    ├── stages/
    │   ├── __init__.py
    │   ├── stage1_pseudonymize.py  # NEW — per doc: detect→pseudonymize→depseudonymize; collect spans, outbound text, restored text, wall-clock
    │   └── stage2_chat_flow.py     # NEW — per doc: chat/completions (echo); leak-audit outbound; check restored answer; collect timing_ms
    ├── scoring/
    │   ├── __init__.py
    │   ├── span_alignment.py       # NEW — align predicted↔gold; primary (same-type + overlap) + strict (exact) variants
    │   ├── detection_metrics.py    # NEW — TP/FP/FN → P/R/F1 per type + micro/macro + confusion matrix (sklearn)
    │   ├── leak_audit.py           # NEW — normalize (case/diacritics/whitespace) + stem match; inflected/partial = FULL leak
    │   └── restoration_metrics.py  # NEW — per-entity outcome (exact/inflection/fuzzy/base-only/missed) + doc exact-restore rate
    ├── latency/
    │   ├── __init__.py
    │   └── timing_collector.py     # NEW — Stage 1 wall-clock per endpoint; Stage 2 parse timing_ms; bucket by length/entity-count
    └── reporting/
        ├── __init__.py
        ├── result_models.py        # NEW — pydantic per-doc + aggregate result types (the on-disk JSON schema)
        ├── tables.py               # NEW — CSV + Typst tables
        ├── figures.py              # NEW — matplotlib/seaborn → PNG/SVG into the configurable out dir
        └── error_analysis.py       # NEW — FN/FP/restoration-failure lists; redacted variants for real-source docs

apps/gateway-eval/tests/
├── conftest.py                     # NEW — env bootstrap + in-process ASGI client (fakeredis + Echo override), seeded builder fixtures
├── corpus/
│   ├── test_synthetic_corpus_builder.py   # NEW — checksum-valid injection; offsets exact; seeded reproducibility
│   ├── test_gold_standard.py              # NEW — offset==text validation; JSONL round-trip; schema errors
│   └── test_real_corpus_loader.py         # NEW — validates annotation; rejects bad offsets
├── scoring/
│   ├── test_span_alignment.py             # NEW — overlap + exact edge cases (adjacent/overlapping/multi-occurrence)
│   ├── test_detection_metrics.py          # NEW — P/R/F1 + micro/macro + confusion matrix correctness
│   ├── test_leak_audit.py                 # NEW — inflected/diacritic/partial forms count as leak; no false leaks on common words
│   └── test_restoration_metrics.py        # NEW — five outcome categories + doc exact-restore rate
├── latency/
│   └── test_timing_collector.py           # NEW — bucketing; Stage 2 timing_ms parsing
└── test_end_to_end.py                     # NEW — small Stage 1 + Stage 2 in-process run → complete report

# --- The ONLY gateway-api touch (additive; Constitution IV) ---
apps/gateway-api/gateway_api/llm_providers/__init__.py   # CHANGED — add "echo/" → EchoProvider factory entry in get_llm_provider
apps/gateway-api/tests/llm_providers/test_llm_router.py  # CHANGED — assert echo/ routes to EchoProvider (provider="echo")

# --- Root wiring ---
.gitignore                           # CHANGED — ignore apps/gateway-eval/gateway_eval/corpus/data/real/
docker-compose / dev docs            # NOTE — document `model: "echo/echo"` for offline eval runs (no new service)
```

**Structure Decision**: A new standalone Nx Python application `apps/gateway-eval` (package
`gateway_eval`), mirroring `apps/gateway-api`'s layout and tooling (`uv`, `ruff`, `pytest`,
`@nxlv/python` executors) but with its **own** `pyproject.toml` so eval-only dependencies never enter the
production gateway image. Module names are role-revealing per
`.claude/rules/python-naming-conventions.md` (no `utils`/`helpers`/`common`/`store`). The gateway-api
package is consumed as a path dependency for corpus construction only. The single additive change to
gateway-api (the `echo/` route) lives in the gateway's provider wiring, not in the harness.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Additive `echo/` provider route in `apps/gateway-api` (spec prose says the harness "changes no gateway behaviour") | Stage 2 must drive the **live** gateway HTTP API with a **deterministic** provider; Echo is currently reachable only via a test-time dependency-override, so it is not selectable over HTTP on the running container. A one-entry factory addition makes `model: "echo/echo"` route to the existing `EchoProvider`. | (a) **Harness-hosted in-process ASGI app** with the Echo override — avoids any gateway change but means Stage 2 no longer exercises the literal `:8000` container the user runs, weakening the "live gateway" guarantee. (b) **Use real Ollama** — non-deterministic, slow on macOS, needs a pulled model, contradicts the "deterministic stub" requirement. The chosen change is additive, Constitution-IV-sanctioned, alters no existing prefix or pipeline behaviour, and is covered by a router test. |
