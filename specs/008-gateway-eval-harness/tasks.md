---
description: "Task list for EPIC 8 (partial) — Gateway PII Evaluation Harness"
---

# Tasks: Gateway PII Evaluation Harness (EPIC 8, partial)

**Input**: Design documents from `specs/008-gateway-eval-harness/`

**Prerequisites**: plan.md, spec.md, research.md (D1–D9), data-model.md, contracts/ (5 files), quickstart.md

**Tests**: INCLUDED — the plan's Testing section explicitly requires unit tests (span alignment, leak
normalization, restoration classification, checksum-valid injection, gold-offset validation) plus one
in-process end-to-end run. Test tasks are written before the implementation they cover within each phase.

**Organization**: grouped by user story (spec.md priorities). US1 + US2 are both P1 → the MVP is the
Stage-1 correctness slice *plus* the zero-leak audit.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1–US5 (story phases only)
- All paths are relative to the repo root. Package root: `apps/gateway-eval/gateway_eval/`; tests:
  `apps/gateway-eval/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the isolated Nx Python app `apps/gateway-eval` (mirrors `apps/gateway-api` tooling).

- [X] T001 Create `apps/gateway-eval/project.json` with Nx targets `evaluate`, `build-corpus`, `lint`, `format`, `test`, `install`, `lock`, `sync` (mirror `apps/gateway-api/project.json` `@nxlv/python` executors; `evaluate`/`build-corpus` use `@nxlv/python:run-commands` invoking `uv run python -m gateway_eval ...`).
- [X] T002 Create `apps/gateway-eval/pyproject.toml`: `requires-python ">=3.12,<4"`; deps `httpx`, `scikit-learn`, `matplotlib`, `seaborn`, `pandas`, `pydantic`, `typer`; dev-group `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-html`, `pytest-sugar`, `fakeredis`, `ruff`; path/editable dependency on `gateway-api` (via `[tool.uv.sources]`); `[tool.hatch.build.targets.wheel] packages = ["gateway_eval"]`.
- [X] T003 [P] Add ruff config (select `E,F,UP,B,SIM,I`, line-length 88) and `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, cov/html report paths) to `apps/gateway-eval/pyproject.toml`, matching gateway-api.
- [X] T004 [P] Create the package skeleton with `__init__.py` files: `gateway_eval/{corpus,gateway_client,stages,scoring,latency,reporting}/` + `corpus/templates/` + `corpus/data/synthetic/` + `corpus/data/real/` (commit a `.gitkeep` in each data dir so they exist on clone; T005 adds the `.gitignore` negation that preserves `data/real/.gitkeep`), and `tests/{corpus,scoring,latency}/`.
- [X] T005 [P] Add the negation pattern to root `.gitignore` so real data is ignored but the dir persists — `apps/gateway-eval/gateway_eval/corpus/data/real/*` plus `!apps/gateway-eval/gateway_eval/corpus/data/real/.gitkeep` (analysis L4); create `apps/gateway-eval/README.md` documenting purpose, `model:"echo/echo"` offline runs, and the RODO/data-handling note (real corpus local-only, never published — research D6).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data shapes, the gold-standard oracle, the entity alias map, and the HTTP client that
**all** stories consume. Scoring imports nothing from `gateway_api` (anti-circularity, D1).

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T006 Create `gateway_eval/config.py` — `EvaluationConfig` (pydantic): `base_url` (default `http://localhost:8000`), `corpus_path`, `out_dir` (default `thesis/images/`), `results_dir`, `stage`, `provider` (`echo`), `seed`, `strict_spans`, `request_timeout_s`, `max_retries`, `length_buckets`, `entity_count_buckets`. No secrets.
- [X] T007 [P] Create `gateway_eval/corpus/gold_standard.py` — `GoldEntity`/`GoldDocument`/`Corpus` pydantic models + JSONL `load_jsonl`/`write_jsonl`/`merge`; enforce the **offset==text invariant** (`text[start:end] == entity.text`), offset bounds, unique `doc_id`, and same-type non-overlap as hard errors (contracts/gold-standard.md).
- [X] T008 [P] Create `gateway_eval/corpus/entity_vocabulary.py` — `CANONICAL_TYPES` (the 10 gold types), `GATEWAY_LABEL_ALIASES` map + `normalize_label()` returning canonical type or `None` (unmapped), and an `is_structured(type)` flag for numeric IDs (research D8).
- [X] T009 Create `gateway_eval/reporting/result_models.py` — all result/report pydantic shapes: `RunConfigSnapshot`, `TypeMetrics`, `DetectionReport`, `LeakFinding`, `LeakReport`, `RestorationDetail`, `RestorationReport`, `LatencySample`, `LatencyReport`, `PerDocumentResult` (leak/restoration/stage2/latency as **Optional** so later stories fill them), `AggregateResult` (data-model.md §5/§7). Scoring modules import these shapes; they live here to avoid import cycles.
- [X] T010 Create `gateway_eval/gateway_client/evaluation_client.py` — async `httpx` client: `health()` gate (refuse if `status != "ok"`), `detect()`, `pseudonymize()`, `depseudonymize()`, `chat_completions()`, `delete_session()`; timeout/retry from config; parse only the response views in contracts/consumed-endpoints.md (extra fields ignored).
- [X] T011 [P] Create `apps/gateway-eval/tests/conftest.py` — env bootstrap (`REDIS_PASSWORD`/`REDIS_ENCRYPTION_KEY`/`REDIS_URL` like gateway-api conftest) before importing the app; an in-process ASGI client fixture (`httpx.ASGITransport` over `gateway_api.main:app`) with `fakeredis` and `get_llm_provider` dependency-overridden to `EchoProvider`; a seeded-builder fixture and a `sample_corpus` fixture path.
- [X] T012 [P] Create `apps/gateway-eval/tests/fixtures/sample_gold.jsonl` — a tiny hand-authored synthetic corpus (5–8 docs covering **all 10** canonical types, valid offsets) so US1/US2 are testable before the full US3 builder exists.
- [X] T013 [P] Create `apps/gateway-eval/tests/corpus/test_gold_standard.py` — offset==text invariant, JSONL round-trip, rejects bad offsets/overlaps, `merge()` counts.
- [X] T014 [P] Create `apps/gateway-eval/tests/test_evaluation_client.py` — against the in-process ASGI app: `health()` gate behaviour and response-view parsing for detect/pseudonymize/depseudonymize.

**Checkpoint**: Foundation ready — story implementation can begin.

---

## Phase 3: User Story 1 — Stage 1 pseudonymization-correctness evaluation (Priority: P1) 🎯 MVP

**Goal**: Per document call `/v1/detect` → `/v1/pseudonymize` → `/v1/depseudonymize`; score detection
(P/R/F1 per type + micro/macro + confusion matrix, recall headline) and round-trip restoration; write
machine-readable per-doc + aggregate results. Ground truth is the gold standard only (D1).

**Independent Test**: run `evaluate --stage 1` against the sample corpus (in-process or live) and confirm
it emits per-type + micro/macro P/R/F1, a confusion matrix, and a restoration breakdown as JSON/CSV.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T015 [P] [US1] `apps/gateway-eval/tests/scoring/test_span_alignment.py` — overlap vs strict-exact; adjacent/overlapping different-type spans; multi-occurrence; greedy one-to-one (D3).
- [X] T016 [P] [US1] `apps/gateway-eval/tests/scoring/test_detection_metrics.py` — TP/FP/FN → P/R/F1, micro vs macro, confusion-matrix cells incl. MISS/SPURIOUS, label normalization + unmapped-label surfacing.
- [X] T017 [P] [US1] `apps/gateway-eval/tests/scoring/test_restoration_metrics.py` — the five outcomes (exact/correct_inflection/fuzzy_recovered/base_form_only/missed), position correctness, document exact-restore rate.

### Implementation for User Story 1

- [X] T018 [P] [US1] `gateway_eval/scoring/span_alignment.py` — `AlignedPair` + `align(gold, predicted, policy)` for `policy ∈ {"overlap","exact"}`, greedy per-type one-to-one (D3).
- [X] T019 [US1] `gateway_eval/scoring/detection_metrics.py` — build `DetectionReport` (per-type + micro/macro + `sklearn` confusion matrix + `unmapped_labels`) from aligned pairs; normalize gateway labels via `entity_vocabulary`; record unmapped predicted labels in `unmapped_labels` **and** count them as false positives in the `SPURIOUS` column so precision stays conservative (research D8 / analysis M2) (depends on T018, T008).
- [X] T020 [P] [US1] `gateway_eval/scoring/restoration_metrics.py` — classify each gold original's recovery into the five outcomes and compute the doc exact-restore rate → `RestorationReport`/`RestorationDetail`.
- [X] T021 [P] [US1] `gateway_eval/latency/timing_collector.py` — Stage 1 wall-clock per endpoint + length/entity-count bucketing → `LatencySample`/`LatencyReport` (D5; Stage 2 timing_ms parsing added in US4).
- [X] T022 [US1] `gateway_eval/stages/stage1_pseudonymize.py` — per doc: fresh `session_id` → `detect`/`pseudonymize`/`depseudonymize` via the client, capture detection spans, `pseudonymized_text`, `restored_text`, and wall-clock; `delete_session` after (depends on T010, T018–T021).
- [X] T023 [US1] `gateway_eval/reporting/results_writer.py` — write `aggregate.json`, `per_document.jsonl`, `detection_per_type.csv` (overlap+exact columns, recall-first), `restoration.csv`, `latency.csv` (depends on T009).
- [X] T024 [US1] `gateway_eval/run_evaluation.py` — orchestrate Stage 1: `health()` gate → load+validate corpus → per-doc Stage 1 → score (overlap + exact) → `RunConfigSnapshot` → write results (depends on T006, T007, T022, T023).
- [X] T025 [US1] `gateway_eval/__main__.py` + CLI (`typer`) `evaluate` command with `--base-url/--corpus/--out/--results/--stage/--strict-spans/--timeout`; exit codes 0/2/3 (contracts/cli.md; leak-fail exit 1 added in US2).
- [X] T026 [US1] `apps/gateway-eval/tests/test_end_to_end.py::test_stage1` — in-process ASGI run over the sample corpus → asserts a complete `AggregateResult` with detection + restoration sections, and that a **second seeded run produces identical aggregate metrics** (SC-006 metrics-reproducibility; analysis L5).

**Checkpoint**: Stage 1 detection + restoration metrics run end to end and emit machine-readable results.

---

## Phase 4: User Story 2 — Inflection-aware PII-leak audit, zero-leak bar (Priority: P1)

**Goal**: For every document, prove no original PII value (incl. inflected/partial forms) survives in the
gateway's outbound text; zero-leak pass bar (Constitution I/VIII).

**Independent Test**: feed a doc whose gold surname appears only inflected (`Kowalskiego`) and confirm it
is reported as a **full leak** with doc/value/type/offset; a clean doc reports zero leaks → exit 0.

### Tests for User Story 2 ⚠️

- [X] T027 [P] [US2] `apps/gateway-eval/tests/scoring/test_leak_audit.py` — inflected form = full leak; diacritic-folded backstop; structured-ID exact (digits-only); word-boundary + length≥4 stem rule avoids false leaks on common words; sub-4 fallback (D4).

### Implementation for User Story 2

- [X] T028 [US2] `gateway_eval/scoring/leak_audit.py` — `audit(doc, outbound_text)`: NFC + lowercase + whitespace-collapse normalization, diacritic-fold secondary pass, structured-ID exact match, stem-prefix match (word-bounded, len≥4) → `LeakFinding` list; aggregate `LeakReport{total_leaks, by_type, by_doc, passed}` (D4).
- [X] T029 [US2] Integrate the leak audit into `gateway_eval/stages/stage1_pseudonymize.py` (audit `pseudonymized_text`) and `gateway_eval/run_evaluation.py` (populate `LeakReport`, drive overall pass/fail).
- [X] T030 [US2] Extend `gateway_eval/reporting/results_writer.py` — add `leaks.csv` (value column **redacted** when `source="real"`) and the leak section of `aggregate.json`.
- [X] T031 [US2] Extend the CLI in `gateway_eval/__main__.py` — exit code `1` when the leak audit finds ≥1 leak (aggregate still written), and a leak pass/fail line in the stdout summary (contracts/cli.md).

**Checkpoint**: The zero-leak audit runs over the corpus, catches inflected leaks, and gates the exit code.

---

## Phase 5: User Story 3 — Reproducible corpus build + privacy-safe real ingestion (Priority: P2)

**Goal**: Seeded synthetic corpus from Polish templates with PII at known offsets (auto gold), plus a
validated ingest path for manually-annotated real contracts kept local-only (D6/D7).

**Independent Test**: build twice with the same `--seed` → byte-identical corpus + gold; ingest a sample
real doc → conforms to the schema and is marked `source="real"`; assembled corpus hits the targets.

### Tests for User Story 3 ⚠️

- [X] T032 [P] [US3] `apps/gateway-eval/tests/corpus/test_synthetic_corpus_builder.py` — checksum-valid IDs (via `gateway_api.pii_detection.checksums`), exact gold offsets, seeded byte-identical reproducibility.
- [X] T033 [P] [US3] `apps/gateway-eval/tests/corpus/test_real_corpus_loader.py` — validates annotation, rejects bad offsets, sets `source="real"`.

### Implementation for User Story 3

- [X] T034 [P] [US3] Author Polish contract templates with typed slots in `gateway_eval/corpus/templates/` — `najem`, `zlecenie`, `o-dzielo`, `sprzedaz` (slots like `{{PERSON:lessor}}`, `{{PESEL:lessor}}`, `{{ADDRESS:property}}`).
- [X] T035 [US3] `gateway_eval/corpus/synthetic_corpus_builder.py` — seeded `FakeDataGenerator(seed)` + `random.Random(seed)`; substitute slots left-to-right recording exact offsets → `GoldDocument`; assert ID validity via `checksums` (regenerate on rare invalid draw); keep per-role identity consistency (depends on T007).
- [X] T036 [P] [US3] `gateway_eval/corpus/real_corpus_loader.py` — load `corpus/data/real/*.jsonl`, validate via `gold_standard`, mark `source="real"`.
- [X] T037 [US3] Add the `build-corpus` CLI command (`--seed/--corpus-out/--count` — distinct flag name from `evaluate --out`, analysis L2) in `gateway_eval/__main__.py` and confirm the Nx `build-corpus` target runs it offline.
- [X] T038 [US3] Generate and **commit** the synthetic corpus to `gateway_eval/corpus/data/synthetic/` so the **synthetic set alone** meets the floor (**≥ 50 docs, ≥ 500 entities, all 10 types**) — CI and reproducibility need no real data; the real 40% is added locally to reach the ~60/40 thesis blend (SC-001, analysis M3).
- [X] T039 [US3] Add corpus-stats + target validation (warn, don't fail) and `Corpus.merge(synthetic, real)` wiring in `gateway_eval/run_evaluation.py`.

**Checkpoint**: A reproducible synthetic corpus exists and real docs can be ingested locally to the same schema.

---

## Phase 6: User Story 4 — Stage 2 full-flow evaluation with Echo + per-stage timing (Priority: P2)

**Goal**: Drive `/v1/chat/completions` with `model="echo/echo"`; confirm declared outbound content is
leak-free and the de-pseudonymized answer reconstructs the original; collect `anonymization_meta.timing_ms`.

**Independent Test**: send a doc through chat with Echo and confirm (a) outbound is leak-free vs gold, (b)
the restored answer reconstructs the original document, (c) a per-stage `timing_ms` breakdown is captured.

### Implementation for User Story 4

- [X] T040 [US4] Add the additive `"echo/": lambda: EchoProvider()` factory entry to `get_llm_provider` in `apps/gateway-api/gateway_api/llm_providers/__init__.py` (contracts/gateway-echo-route.md; Constitution IV — no other gateway change).
- [X] T041 [P] [US4] Update `apps/gateway-api/tests/llm_providers/test_llm_router.py` — assert `model="echo/echo"` dispatches to `EchoProvider` (`provider="echo"`, `finish_reason="stop"`) and the three existing prefixes + unknown-model 400 are unaffected.
- [X] T042 [US4] `gateway_eval/stages/stage2_chat_flow.py` — per doc: `chat_completions(model="echo/echo")`; leak-audit `input_anonymization.pseudonymized_content` (reuse `leak_audit`); assert the restored answer reconstructs the original; capture `anonymization_meta.timing_ms`; fresh session + `delete_session` (depends on T010, T028).
- [X] T043 [US4] Extend `gateway_eval/latency/timing_collector.py` — parse Stage 2 `timing_ms` (`ner_analysis`/`fake_generation`/`redis_write`/`llm_request`/`deanonymization`/`total`) into `LatencySample`s with the same buckets (D5).
- [X] T044 [US4] Extend `gateway_eval/run_evaluation.py` + CLI for `--stage 2|both` and `--provider echo`; populate `PerDocumentResult.stage2` and `AggregateResult.stage2_summary`.
- [X] T045 [P] [US4] `apps/gateway-eval/tests/latency/test_timing_collector.py` — Stage 1 wall-clock bucketing + Stage 2 `timing_ms` parsing.
- [X] T046 [US4] Extend `apps/gateway-eval/tests/test_end_to_end.py::test_both_stages` — in-process ASGI (fakeredis + Echo override) run of `--stage both` → complete `AggregateResult` incl. the `stage2_summary`, and assert a re-run yields identical aggregate metrics (SC-006).

**Checkpoint**: The integrated chat flow is validated offline with Echo and the timing breakdown is collected.

---

## Phase 7: User Story 5 — Thesis-ready outputs + error analysis (Priority: P2)

**Goal**: Render publication-ready figures + Typst tables into the configurable out dir and produce an
error-analysis report — only aggregate metrics + redacted examples published (D6).

**Independent Test**: after a run, confirm the four figure types render to `--out`, Typst tables exist, and
`error_analysis.md` lists concrete FN/FP/restoration failures with real-source originals redacted.

### Implementation for User Story 5

- [X] T047 [P] [US5] `gateway_eval/reporting/figures.py` — `matplotlib`/`seaborn` → PNG+SVG into `--out`: `confusion_matrix` heatmap, `prf1_by_type` (recall emphasized), `latency_distribution` (faceted by bucket), `restoration_outcomes` (stacked).
- [X] T048 [P] [US5] `gateway_eval/reporting/tables.py` — Typst `#table(...)` snippets (`*.typ`) + CSV mirror: per-type detection (recall-first), latency summary, restoration outcomes; no real originals.
- [X] T049 [P] [US5] `gateway_eval/reporting/error_analysis.py` — emit `error_analysis.md` listing FN/FP/restoration-failure/leak cases; **redact** originals for `source="real"` (type + synthetic stand-in), allow synthetic originals (FR-031/FR-032).
- [X] T050 [US5] Wire `figures` + `tables` + `error_analysis` into `gateway_eval/run_evaluation.py` (write into `--out`); assert publishable artifacts carry no real originals.
- [X] T051 [P] [US5] `apps/gateway-eval/tests/reporting/test_reporting.py` — figures render to files; `error_analysis` redacts real-source originals; `aggregate.json` is originals-free.

**Checkpoint**: All thesis evidence (figures, tables, error analysis) is produced and privacy-safe.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T052 [P] Update dev docs / root README + docker note: `model:"echo/echo"` for offline eval, rebuild `gateway-api` image after adding the echo route, and the RODO data-handling summary.
- [X] T053 [P] Run `nx run gateway-eval:lint` + `format`; verify role-revealing names per `.claude/rules/python-naming-conventions.md` (no `utils/helpers/common/store`).
- [X] T054 Run `quickstart.md` end to end (`build-corpus`, `--stage 1`, `--stage 2`, `--stage both`, `nx run gateway-eval:test`) and tick the quickstart validation checklist (SC-001…SC-010).
- [X] T055 [P] Verify `.gitignore` excludes `corpus/data/real/` contents (negation keeps `.gitkeep`) and that no real PII appears in any committed or `thesis/images/` artifact (SC-007).
- [X] T056 [P] Add an anti-circularity guard `apps/gateway-eval/tests/test_no_circular_ground_truth.py` — assert (via an import/AST scan) that no module under `gateway_eval/scoring/` imports `gateway_api`, and that scoring functions take only gold + HTTP-response views as the reference (never `entities_replaced`/session mappings) — FR-002, Constitution I/II; analysis M4.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. **BLOCKS all stories.**
- **US1 (Phase 3, P1)**: depends on Foundational. The MVP core.
- **US2 (Phase 4, P1)**: depends on Foundational; edits US1's `stage1_pseudonymize.py`/`run_evaluation.py`/`results_writer.py`/CLI → sequence **after US1**.
- **US3 (Phase 5, P2)**: depends on Foundational (`gold_standard`) + `checksums` from gateway-api; independent of US1/US2 logic (can run in parallel with them), but T038 (commit the synthetic corpus) makes the synthetic set independently meet the ≥50-doc / ≥500-instance floor.
- **US4 (Phase 6, P2)**: depends on Foundational + the `leak_audit` from US2 (T028) for the outbound audit; the gateway echo route (T040) is independent and can be done any time.
- **US5 (Phase 7, P2)**: depends on the reports produced by US1/US2 (+US4 for stage2 figures) — sequence **last** among stories.
- **Polish (Phase 8)**: after all desired stories.

### Story dependencies (summary)

- US1 → none (after Foundational).
- US2 → Foundational; touches US1 files (sequence after US1).
- US3 → Foundational; otherwise independent.
- US4 → Foundational + US2's `leak_audit` (T028); gateway echo route additive.
- US5 → US1/US2 (+US4) result data.

### Within each story

- Tests (where present) are written before the implementation they cover.
- Models/shapes → scoring → stages → orchestration/CLI → end-to-end test.

---

## Parallel Opportunities

- **Setup**: T003, T004, T005 in parallel.
- **Foundational**: T007, T008 in parallel; T011, T012, T013, T014 in parallel (after T006/T007/T009/T010 exist).
- **US1 tests**: T015, T016, T017 in parallel. **US1 impl**: T018, T020, T021 in parallel (T019 after T018; T022 after T018–T021).
- **US3**: T032, T033 in parallel; T034, T036 in parallel.
- **US4**: T040/T041 (gateway side) in parallel with T042–T046 prep.
- **US5**: T047, T048, T049 in parallel; T050 after them; T051 in parallel once files exist.
- **Cross-story**: with capacity, US3 can proceed in parallel with US1/US2 (disjoint files); US5 must wait on result data.

### Parallel example — US1

```bash
# Tests first (all parallel):
Task: "test_span_alignment.py"   # T015
Task: "test_detection_metrics.py" # T016
Task: "test_restoration_metrics.py" # T017

# Then independent implementation files in parallel:
Task: "scoring/span_alignment.py"      # T018
Task: "scoring/restoration_metrics.py" # T020
Task: "latency/timing_collector.py"    # T021
```

---

## Implementation Strategy

### MVP (both P1 stories)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 (US1) → **STOP & VALIDATE**: `evaluate --stage 1` over the sample corpus emits detection +
   restoration metrics (in-process e2e green).
3. Phase 4 (US2) → the zero-leak audit gates the run. **This is the true MVP** — both P1 stories deliver
   the headline thesis results (detection quality + the privacy proof).

### Incremental delivery

US3 (full reproducible corpus) → US4 (Stage 2 + timing) → US5 (figures/tables/error analysis) → Polish.
Each story adds value without breaking earlier ones; stop at any checkpoint to validate independently.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Anti-circularity (D1, FR-002): nothing under `scoring/` imports `gateway_api`; the only gateway-api imports
  are in `corpus/synthetic_corpus_builder.py` (FakeDataGenerator) and via `checksums`. Enforced by the T056 guard.
- The single gateway-api change is the additive `echo/` route (T040/T041) — Constitution IV, no existing
  behaviour altered.
- Real corpus + any gold with real originals stay under the git-ignored `corpus/data/real/`; only aggregate
  metrics + redacted examples reach `thesis/images/` (D6).
- Commit after each task or logical group.
