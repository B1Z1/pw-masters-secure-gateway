# Phase 1 Data Model: EPIC 2 — PII Detection Engine

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

This epic stores nothing. The "data model" is the set of **in-memory / on-the-wire** structures the
engine produces and the **read-only configuration** it consumes. No database, no Redis, no persistence.

---

## 1. `DetectedEntity` (output DTO)

The single unit returned by `DetectionEngine.detect()` and serialized by `POST /v1/detect`
(`detection/dto.py`, pydantic model). Maps FR-002.

| Field | Type | Notes |
|---|---|---|
| `entity_type` | `str` | One of the entity types in §3. |
| `start` | `int` | Inclusive start offset into the **original** input (UTF-8/codepoint index). |
| `end` | `int` | Exclusive end offset into the original input. |
| `score` | `float` | Confidence in `[0.0, 0.99]` (clamped — research D6). |
| `text` | `str` | Exactly `original_text[start:end]`, including any separators (FR-003, SC-002). |
| `metadata` | `dict` | Type-specific; `{}` when none. Schemas in §4. |

**Invariants**
- `0 <= start < end <= len(text_input)`.
- `text == text_input[start:end]` (validated in `test_engine.py`).
- `score` reflects the deterministic scoring method (§5); always ≤ 0.99.
- After the engine's threshold post-filter, no returned entity has `score < threshold[entity_type]`.
- After the overlap pass (research D4), no returned entity is fully contained within another.

---

## 2. Recognizer descriptors (internal)

Each recognizer (`detection/recognizers/*.py`) contributes candidates for one entity type. Conceptual
shape (not a serialized object): `{ entity_type, patterns | model-source, context_words, base_score,
validator?, metadata_builder? }`. The per-recognizer contract is enumerated in
[contracts/recognizers.md](contracts/recognizers.md).

| Recognizer | Entity type | Source | Checksum | Metadata |
|---|---|---|---|---|
| `PeselRecognizer` | `PESEL` | regex + `ChecksumPatternRecognizer` | PESEL control sum | gender, birth_date, checksum_valid, normalized |
| `NipRecognizer` | `NIP` | regex + checksum base | NIP control sum | checksum_valid, normalized |
| `RegonRecognizer` | `REGON` | regex (9 & 14) + checksum base | REGON-9 / REGON-14 | variant, checksum_valid, normalized |
| `PolishBankAccountRecognizer` | `POLISH_BANK_ACCOUNT` | regex + checksum base | ISO 7064 mod-97 | format(IBAN/NRB), mod97_valid, normalized |
| `PolishAddressRecognizer` | `POLISH_ADDRESS` | regex (multi-line) | — | has_street, postal_code |
| `DateRecognizer` (PL) | `DATE_TIME` | regex (numeric + worded) | — | kind(numeric/worded) |
| *base* PERSON | `PERSON` | spaCy `persName` (mapped) | — | — |
| *base* LOCATION | `LOCATION` | spaCy `placeName`/`geogName` | — | — |
| *base* EMAIL | `EMAIL_ADDRESS` | Presidio `EmailRecognizer` | — | — |
| *base* PHONE | `PHONE_NUMBER` | Presidio `PhoneRecognizer` (region PL) | — | — |

---

## 3. Entity-type vocabulary

Base (Presidio names, reused): `PERSON`, `LOCATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `DATE_TIME`.
Custom (added this epic): `PESEL`, `NIP`, `REGON`, `POLISH_BANK_ACCOUNT`, `POLISH_ADDRESS`.

These strings are the keys in the threshold config (§6) and the `entity_type` field of `DetectedEntity`.

---

## 4. Metadata schemas (per entity type)

All keys optional unless noted; values are emit-only (never stored).

```text
PESEL                : { gender: "male"|"female", birth_date: "YYYY-MM-DD"|null,
                         checksum_valid: bool, normalized: "<11 digits>" }
NIP                  : { checksum_valid: bool, normalized: "<10 digits>" }
REGON                : { variant: "9"|"14", checksum_valid: bool, normalized: "<9|14 digits>" }
POLISH_BANK_ACCOUNT  : { format: "IBAN"|"NRB", mod97_valid: bool, normalized: "<26 digits>" }
POLISH_ADDRESS       : { has_street: bool, postal_code: "XX-XXX"|null }
DATE_TIME            : { kind: "numeric"|"worded" }
PERSON|LOCATION|EMAIL_ADDRESS|PHONE_NUMBER : {}
```

`normalized` is the separator-stripped value used for validation (research D, normalization). It is
metadata only; `text`/`start`/`end` still reference the original span.

---

## 5. Score bands (deterministic — research D6)

Pipeline: `base → checksum adjustment → + context bonus (if label) → clamp [0, 0.99]`.

Constants (`scoring.py`): `S_VALID = 0.80`, `S_INVALID = 0.30`; context via
`LemmaContextAwareEnhancer(context_similarity_factor = 0.20, min_score_with_context_similarity = 0.0)`;
final clamp `0.99`.

| Situation | Pre-context | + context label |
|---|---|---|
| National ID / bank — checksum **valid** | 0.80 | **0.99** |
| National ID / bank — checksum **invalid** (kept, not dropped) | 0.30 | 0.50 |
| Address **with** street | 0.60 | 0.80 |
| Address **without** street (postal code + city) | 0.40 | 0.60 |
| Date — numeric | 0.60 | 0.80 |
| Date — worded | 0.55 | 0.75 |
| PERSON / LOCATION (model) | 0.85 | **0.99** |
| EMAIL_ADDRESS | 0.80 | — |
| PHONE_NUMBER (PL) | `phonenumbers`/Presidio default | + 0.20 with label |

These are defaults driven by the rule set, not per-value literals (FR-015, FR-016). They are the
contract the thesis describes as "the scoring method".

---

## 6. Threshold configuration (read-only, live)

`detection/default_thresholds.yaml` (shipped), overridable via `DETECTION_THRESHOLDS_PATH`. Loaded by
`thresholds.py` with mtime-based live reload (research D5). Schema and defaults:
[contracts/thresholds.md](contracts/thresholds.md). Shape:

```yaml
default: 0.30                 # applied to any entity_type not listed below
thresholds:
  PESEL: 0.25
  NIP: 0.25
  REGON: 0.25
  POLISH_BANK_ACCOUNT: 0.25
  POLISH_ADDRESS: 0.35
  DATE_TIME: 0.30
  PERSON: 0.40
  LOCATION: 0.40
  EMAIL_ADDRESS: 0.40
  PHONE_NUMBER: 0.40
```

**Rules**: an entity is kept iff `score >= threshold[entity_type]` (else `default`). `0.0` = "paranoid"
(surface everything the recognizer produced); `1.0` = disabled (nothing passes, since `score ≤ 0.99`).
Editing the file changes behaviour on the **next** request — no restart (FR-020). Defaults are low by
design (recall over precision; bad-checksum band 0.30 ≥ 0.25 → still surfaced, FR-014).

---

## 7. Model-readiness status (feeds `/health`)

A process-level boolean (`detection/nlp.py: is_model_ready()`), set by the eager background load at
startup (research D8). Not persisted. Consumed by:
- `health.check_spacy_model()` → `"ok"` / `"unavailable"` (FR-028);
- `POST /v1/detect` readiness dependency → HTTP 503 when false (FR-030).

**Loading model**: the spaCy singleton **lazily loads on first `detect()`** if the eager startup load
has not (yet) run — so the engine is usable, and US1 is independently demoable, before US5 wires the
eager background load. US5's startup load simply makes readiness observable up front (and 503-gates
detect until ready) rather than paying the load cost on the first request.

State transitions: `loading → ready` (load success) or `loading → unavailable` (load failure, logged,
no crash); re-evaluated only at startup (a model that fails to load does not retry per request this
epic — documented limitation).
