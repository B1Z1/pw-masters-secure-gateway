# Data Model: EPIC 8 (partial) — Gateway PII Evaluation Harness

**Feature**: `specs/008-gateway-eval-harness` | **Date**: 2026-06-25

All models are `pydantic` (or frozen dataclasses where noted) in the `gateway_eval` package. Two model
families: **corpus / gold standard** (the oracle, on disk as JSONL) and **results** (what a run produces,
on disk as JSON/CSV). Nothing here imports gateway-api scoring internals (D1).

---

## 1. Gold standard (`corpus/gold_standard.py`)

The single shared schema for both synthetic and real documents. One JSON object **per line** (JSONL).

### `GoldEntity`

| Field | Type | Notes |
|-------|------|-------|
| `type` | `str` | Canonical gold vocabulary only (§4). |
| `start` | `int` | Character offset into `GoldDocument.text` (inclusive). |
| `end` | `int` | Character offset (exclusive). |
| `text` | `str` | The original PII surface as it appears in `text`. |

**Validation** (enforced on load and on build): `0 <= start < end <= len(text)` **and**
`text[start:end] == entity.text` (the offset/text invariant — a wrong offset is a hard error, never a
silent skip). Entities are sorted by `start`; overlapping entities of the **same** type are rejected,
adjacent/overlapping entities of **different** types are allowed (and exercised by tests).

### `GoldDocument`

| Field | Type | Notes |
|-------|------|-------|
| `doc_id` | `str` | Unique within the corpus (e.g. `syn-najem-001`, `real-zlecenie-007`). |
| `source` | `"synthetic" \| "real"` | Drives publication policy (real ⇒ redact before publishing). |
| `contract_type` | `str` | `najem` \| `zlecenie` \| `o-dzielo` \| `sprzedaz` (extensible). |
| `text` | `str` | Full document text. |
| `entities` | `list[GoldEntity]` | All known PII instances. |

### `Corpus`

In-memory collection of `GoldDocument` plus derived counts. Validation against targets (warning, not hard
fail, so a partial corpus is still runnable): `>= 50` documents, `>= 500` total entities, all 10 canonical
types present, synthetic/real ratio ≈ 60/40. IO: `load_jsonl(path)`, `write_jsonl(path, docs)`,
`merge(synthetic_dir, real_dir)`.

---

## 2. Corpus construction (`corpus/synthetic_corpus_builder.py`, `real_corpus_loader.py`)

### Synthetic build (seeded, reproducible — D7)

A **template** is a string with typed slots (e.g. `{{PERSON:lessor}}`, `{{PESEL:lessor}}`,
`{{ADDRESS:property}}`). The builder:
1. Seeds `FakeDataGenerator(seed)` and `random.Random(seed)`.
2. For each slot, generates a realistic value via `FakeDataGenerator` (PERSON gender-consistent, etc.) and,
   for numeric IDs, asserts validity through `pii_detection.checksums` (`pesel_is_valid`, `nip_is_valid`,
   `regon9_is_valid`/`regon14_is_valid`, `nrb_is_valid`) — regenerating on the rare invalid draw.
3. Substitutes slots left-to-right, recording the **exact character offset** of each inserted value → a
   `GoldEntity`. Because the builder places the value, offsets are known with zero annotation effort.
4. Keeps role consistency: the same role (`lessor`) reuses the same generated identity across slots within a
   document.

Output: one `GoldDocument` (`source="synthetic"`) per generated contract, written to
`corpus/data/synthetic/*.jsonl` (committed).

### Real ingest (`real_corpus_loader.py`)

Loads `corpus/data/real/*.jsonl` (git-ignored), runs the **same** `GoldDocument`/`GoldEntity` validation
(offset==text invariant), and marks `source="real"`. Manual annotation is done by the researcher to this
schema; the loader is the gatekeeper that rejects malformed offsets.

---

## 3. Gateway response views (consumed, not owned — `gateway_client/evaluation_client.py`)

Thin read models the client parses from gateway responses. These are **predictions under test**, never
ground truth (D1). Only the fields the harness relies on are modelled (extra fields ignored).

| Endpoint | Parsed into |
|----------|-------------|
| `GET /health` | `HealthView{status, dependencies}` — gate: refuse to run if `status != "ok"`. |
| `POST /v1/detect` | `list[DetectedSpan{entity_type, start, end, score, text}]`. |
| `POST /v1/pseudonymize` | `PseudonymizeView{pseudonymized_text, entities_replaced:[{entity_type, original, fake, start, end}], session_id}`. |
| `POST /v1/depseudonymize` | `DepseudonymizeView{restored_text, session_id}`. |
| `POST /v1/chat/completions` | `ChatView{answer (choices[0].message.content), session_id, input_anonymization{pseudonymized_content, replacements}, anonymization_meta{entities_detected, total_entities, provider, timing_ms{...}}}`. |
| `DELETE /v1/sessions/{id}` | status only (cleanup). |

> **Note on `entities_replaced` / `input_anonymization`**: the harness uses `pseudonymized_text` /
> `input_anonymization.pseudonymized_content` as the **outbound text to audit for leaks** (legitimate — the
> oracle is the gold originals). It does **not** treat `entities_replaced` as the detection answer key.

---

## 4. Entity vocabulary + alias map (`corpus/entity_vocabulary.py`)

`CANONICAL_TYPES = ("PERSON","LOCATION","ADDRESS","PESEL","NIP","REGON","BANK_ACCOUNT","EMAIL_ADDRESS",
"PHONE_NUMBER","DATE_TIME")`.

`GATEWAY_LABEL_ALIASES: dict[str, str]` — the versioned map from gateway labels to canonical types (full
table in research.md D8). `normalize_label(label) -> str | None` returns the canonical type or `None` for
an unmapped label. An unmapped predicted span is both **surfaced** in `DetectionReport.unmapped_labels`
**and counted as a false positive** (`SPURIOUS`), so precision stays conservative (research D8, M2). Each
numeric-ID type also carries an `is_structured` flag used by the leak matcher (D4).

---

## 5. Scoring entities

> **Where these shapes live (resolves analysis M1)**: every result/report data type below (`TypeMetrics`,
> `DetectionReport`, `LeakFinding`, `LeakReport`, `RestorationDetail`, `RestorationReport`, plus
> `LatencySample`/`LatencyReport` in §6) is **defined once in `reporting/result_models.py`** (§7). The
> `scoring/` and `latency/` modules **import** these shapes and hold only the computation logic — a one-way
> dependency that avoids import cycles. `AlignedPair` is the lone exception: an internal scoring type
> defined in `span_alignment.py`.

### `span_alignment.py`
- `AlignedPair{gold: GoldEntity | None, predicted: DetectedSpan | None, match_kind: "exact"|"overlap"|"fp"|"fn"}`.
- `align(gold, predicted, policy) -> list[AlignedPair]` — greedy per-type one-to-one (D3). `policy ∈
  {"overlap","exact"}`.

### `detection_metrics.py`
- `TypeMetrics{type, tp, fp, fn, precision, recall, f1, support}`.
- `DetectionReport{per_type: list[TypeMetrics], micro: TypeMetrics, macro: TypeMetrics,
  confusion_matrix: 2D counts over CANONICAL_TYPES + {MISS, SPURIOUS}, policy: "overlap"|"exact",
  unmapped_labels: dict[str,int]}`. Confusion matrix built via `sklearn.metrics.confusion_matrix` over the
  aligned (gold-type, predicted-type) pairs. Unmapped predicted labels are recorded in `unmapped_labels`
  **and** folded into the `SPURIOUS` column as false positives, so they lower precision (M2).

### `leak_audit.py`
- `LeakFinding{doc_id, type, original, form_found, start, end, match_mode: "exact_id"|"stem"|"diacritic_fold"}`.
- `audit(doc, outbound_text) -> list[LeakFinding]` (D4). Aggregated into
  `LeakReport{total_leaks, by_type, by_doc, passed: total_leaks == 0}`.

### `restoration_metrics.py`
- `RestorationOutcome ∈ {"exact","correct_inflection","fuzzy_recovered","base_form_only","missed"}`.
- `RestorationDetail{doc_id, type, original, outcome, restored_surface, position_correct: bool}`.
- `RestorationReport{by_outcome: dict[outcome,int], by_type: dict[type, dict[outcome,int]],
  doc_exact_restore_rate: float}` — a document is "exactly restored" when every gold original is recovered
  with outcome `exact` at the correct position.

---

## 6. Latency (`latency/timing_collector.py`)

- `LatencySample{doc_id, stage: 1|2, channel: "detect"|"pseudonymize"|"depseudonymize"|"ner_analysis"|
  "fake_generation"|"redis_write"|"llm_request"|"deanonymization"|"total", ms: float,
  length_bucket: str, entity_count_bucket: str}`.
- Buckets: length by character count (e.g. `<500`, `500–1500`, `1500–3000`, `>3000`); entity count
  (`0–5`, `6–15`, `16–30`, `>30`) — thresholds in `config.py`.
- `LatencyReport{by_channel: {channel: {p50,p90,p99,mean,n}}, by_length_bucket, by_entity_bucket}`.

---

## 7. Result envelope (`reporting/result_models.py`) — the on-disk JSON schema

### `RunConfigSnapshot` (D7 traceability)
`{seed, base_url, gateway_health, corpus_version_hash, span_policy, provider, started_at, finished_at,
gateway_eval_version}`.

### `PerDocumentResult`
`{doc_id, source, contract_type, n_gold_entities, detection: {overlap: DetectionReport-slice, exact: …},
leaks: list[LeakFinding], restoration: list[RestorationDetail], latency: list[LatencySample],
stage2: {leak_free: bool, answer_restored: bool, timing_ms: {...}} | null, errors: list[str]}`.

> Per-document results may embed original PII (synthetic or real). For `source="real"` they are treated as
> sensitive (kept with the git-ignored real data, never published) — only aggregates and redacted examples
> are promoted (D6).

### `AggregateResult`
`{config: RunConfigSnapshot, corpus_stats: {n_docs, n_entities, by_type, by_source, split_ratio},
detection: {overlap: DetectionReport, exact: DetectionReport}, leak: LeakReport,
restoration: RestorationReport, latency: LatencyReport, stage2_summary: {n_docs, n_leak_free,
n_answer_restored} | null}`.

This `AggregateResult` is the publishable artifact (it carries no originals — only counts/metrics) and the
source for every table and figure.

---

## 8. Configuration (`config.py`)

`EvaluationConfig` (pydantic `BaseSettings`-style, CLI-overridable): `base_url`, `corpus_path`,
`out_dir` (default `thesis/images/`), `results_dir` (machine-readable JSON/CSV; sibling of out_dir),
`stage`, `provider` (`echo`), `seed`, `strict_spans: bool`, `request_timeout_s`, `max_retries`,
`length_buckets`, `entity_count_buckets`. No secrets — the harness needs none (no auth, Echo provider).
