# Phase 0 Research & Decisions: EPIC 2 — PII Detection Engine

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-06-16

The implementation approach was supplied in detail with the `/speckit-plan` request and is fixed by the
constitution (Presidio + spaCy `pl_core_news_lg`). There are therefore **no open `NEEDS CLARIFICATION`
items**. This document records the binding decisions, including two refinements where the verified
Presidio API differs from the literal instruction (D3, D4). Presidio behaviour below was verified
against the official docs (microsoft.github.io/presidio).

---

## D1 — Detection built on Presidio `AnalyzerEngine` + spaCy `pl_core_news_lg` (singleton)

**Decision**: Wrap a single `AnalyzerEngine` behind a `DetectionEngine` class exposing
`detect(text: str) -> list[DetectedEntity]`. The spaCy model is loaded **once** as a process singleton
(`detection/nlp.py`) and reused across requests.

**Rationale**: Mandated NER stack (Constitution VI / Technology Constraints). `pl_core_news_lg` is large;
loading per request would dominate latency. The model is already baked into the backend image
(`apps/gateway-api/Dockerfile` line 38: `python -m spacy download pl_core_news_lg`), so the container
never downloads at runtime.

**Alternatives considered**: Raw spaCy + hand-rolled regex (rejected — reinvents Presidio's recognizer
registry, context enhancer, and conflict handling); transformer NER (rejected — not the mandated stack,
heavier, no benefit at thesis scale).

**NlpEngine configuration** (`NlpEngineProvider`):

```text
nlp_engine_name: spacy
models: [{ lang_code: "pl", model_name: "pl_core_news_lg" }]
AnalyzerEngine(nlp_engine=…, supported_languages=["pl"], registry=…, context_aware_enhancer=…)
analyze(text, language="pl", …)
```

---

## D2 — NKJP → Presidio entity-label mapping (critical for PERSON/LOCATION)

**Decision**: Configure the NlpEngine's `ner_model_configuration.model_to_presidio_entity_mapping` to map
the Polish model's NKJP labels to Presidio entity types:

| `pl_core_news_lg` label | Presidio entity type |
|---|---|
| `persName` | `PERSON` |
| `placeName` | `LOCATION` |
| `geogName` | `LOCATION` |
| `date` | `DATE_TIME` |
| `time` | `DATE_TIME` |
| `orgName` | `ORGANIZATION` *(out of scope; mapped but not surfaced / low priority)* |

**Rationale**: Presidio's **default** spaCy mapping targets English labels (`PERSON`, `GPE`, `LOC`, …).
`pl_core_news_lg` emits NKJP labels (`persName`, `placeName`, `geogName`, …). Without remapping, the base
recognizers would silently detect **nothing** for PERSON/LOCATION — the single most likely Epic-2
integration bug. This mapping is the fix.

**Alternatives**: A custom `EntityRecognizer` reading `nlp_artifacts.entities` directly (rejected —
duplicates what the mapping already does cleanly).

**Note**: The custom Polish `DateRecognizer` (D-dates) is the primary DATE_TIME source; the model's `date`
label supplements it and is merged by the overlap pass (D4).

---

## D3 — Checksum scoring via explicit score bands (NOT `validate_result` True/False)

**Decision**: National-ID recognizers subclass a thin `ChecksumPatternRecognizer(PatternRecognizer)`
that runs the regex via the base class, then **assigns the score explicitly** from the checksum result —
valid → high band, invalid → low band — and attaches metadata. It does **not** use Presidio's
`validate_result()` boolean contract for the invalid case.

**Rationale (verified against Presidio source)**: In `PatternRecognizer`, when `validate_result()`
returns:
- `True`  → `score = EntityRecognizer.MAX_SCORE` (1.0)
- `False` → `score = EntityRecognizer.MIN_SCORE` (0.0), and the result is then **dropped**
  (`if pattern_result.score > MIN_SCORE: results.append(...)`).

A dropped result directly violates **FR-014** and the spec edge case "PESEL with an invalid control-sum:
still surfaced … with low confidence rather than dropped". It would also make a random 11-digit string
that *fails* the checksum disappear, contradicting recall-over-precision. We therefore assign scores
ourselves so invalid matches are **kept** at a low band.

**Mechanism**: set the recognizer's `Pattern.score` to the invalid/low band (so the base `analyze()`
yields the match without dropping it), then override `analyze()` to (a) recompute the checksum on the
normalized span, (b) set `result.score` to the valid band when it passes, (c) stash metadata in
`result.recognition_metadata`. The `LemmaContextAwareEnhancer` then adds the context bonus.

**Alternatives**: Return `None` from `validate_result` for invalid (keeps base score) — workable but
cannot distinguish "checksum failed" from "not checked" and cannot raise valid matches to a distinct
band without also hardcoding MAX_SCORE. The explicit-band override is clearer and fully deterministic.

---

## D4 — Deterministic overlap resolution in the engine (NOT anonymizer `ConflictResolutionStrategy`)

**Decision**: After mapping to DTOs, run an explicit, deterministic **overlap-resolution pass**:
sort by span length (desc), then start; drop any entity whose span is fully contained in an
already-accepted longer entity; additionally, a `POLISH_ADDRESS` span subsumes any `LOCATION` /
city candidate contained within it.

**Rationale (verified)**: `ConflictResolutionStrategy.MERGE_SIMILAR_OR_CONTAINED` /
`REMOVE_INTERSECTIONS` belong to the **AnonymizerEngine** (doc source: `api/anonymizer_python`), which
this epic does not use, and the analyzer's same-type merge only handles **identical** entity types.
The spec's overlap cases are **cross-type**: NIP (10) ⊂ PESEL (11), 9-digit REGON ⊂ 14-digit REGON,
city ⊂ address. A "longest/containing span wins" pass handles all of these uniformly and is trivially
testable and explainable — preferable to relying on Presidio's score-based internal de-duplication
(which is order/score-sensitive and would not guarantee the longer span wins when scores tie).

**Interaction with FR-026** (first+last name may be one or two PERSON spans): the pass only removes
*contained* spans; two *adjacent, non-overlapping* PERSON spans are both kept — satisfying the "either
outcome acceptable" rule.

---

## D5 — Per-type thresholds as a post-filter from a live YAML file

**Decision**: Thresholds live in `detection/default_thresholds.yaml` (overridable via
`DETECTION_THRESHOLDS_PATH`). `thresholds.py` loads them and **re-reads on file change** (cache keyed on
the file's mtime). Filtering happens **after** analysis + context enhancement + overlap resolution:
each entity is dropped if `score < threshold[entity_type]` (falling back to a `default` key).

**Rationale**: `AnalyzerEngine.analyze()` accepts only a single global `score_threshold`, so per-type
minimums cannot be expressed there. A post-filter gives per-type control and, by reading the file live,
satisfies FR-020 "takes effect without restarting" — verified against the spec clarification that
thresholds live in a dedicated file **separate from the cached env `Settings`** and must **not**
re-introduce a Redis dependency on the detect path.

**Alternatives**: Env vars (rejected — cached by `@lru_cache get_settings()`; awkward to change in a
running container); Redis-backed config (rejected by spec clarification — would couple the stateless
detect path to Redis); an admin API (deferred — more surface than the thesis needs, Constitution IX).

**mtime-reload vs per-request read**: mtime caching avoids a file read on every request while still
reflecting edits on the next request after the file changes — the cheapest way to honour "no restart".

---

## D6 — Deterministic, explainable score bands + clamp to ≤ 0.99

**Decision**: Scores are produced by fixed rules, not literals per value:

```
base pattern score  →  adjusted by checksum (valid/invalid band)  →  + fixed context bonus (if label)
                    →  clamped to [0.0, 0.99]
```

Constants (`scoring.py`): `S_VALID = 0.80`, `S_INVALID = 0.30`, `S_FORMAT_*` per non-checksum recognizer,
context via `LemmaContextAwareEnhancer(context_similarity_factor = 0.20, min_score_with_context_similarity = 0.0)`.
Resulting bands (full table in [data-model.md](data-model.md) and [contracts/recognizers.md](contracts/recognizers.md)):

| Case | score |
|---|---|
| checksum valid + context label | ≈ 0.99 (0.80 + 0.20, clamped) |
| checksum valid, no label | ≈ 0.80 |
| checksum invalid + label | ≈ 0.50 |
| checksum invalid, no label | ≈ 0.30 |
| format-only recognizer (address/date) | recognizer base (+0.20 with label) |
| PERSON / LOCATION (model) | 0.85 base (+0.20 with label → 0.99) |

**Rationale**: A documented rule set is what lets the thesis "describe scoring as a consistent method".
`min_score_with_context_similarity = 0.0` disables Presidio's default 0.4 floor, which would otherwise
lift a bad-checksum value to ≥ 0.4 on any nearby label and blur the valid/invalid distinction. Clamping
to **0.99** reserves 1.0 so a configured threshold of `1.0` reliably disables a type (FR-022), and makes
"valid + labelled ≈ 0.99" exact.

**Determinism**: spaCy NER decoding is deterministic for a fixed model version; Presidio assigns a fixed
default score to model entities; all custom scores are constants. Identical input + identical config →
identical output (SC-005).

---

## D7 — Project DTO `DetectedEntity` at the engine boundary

**Decision**: `detect()` returns a list of `DetectedEntity` (pydantic model):
`entity_type: str`, `start: int`, `end: int`, `score: float`, `text: str`, `metadata: dict`. Presidio
`RecognizerResult` objects are mapped into this DTO at the engine boundary; `text` is sliced from the
original input by `[start:end]` so it always matches exactly (SC-002).

**Rationale**: Decouples the rest of the system (and later epics' substitution engine) from Presidio
internals, and provides a `metadata` channel that `RecognizerResult` lacks. Metadata is **emitted only**
— nothing is stored (no Redis, no session) this epic.

**Metadata carried** (see [data-model.md](data-model.md)): PESEL `{gender, birth_date, checksum_valid,
normalized}`; REGON `{variant, checksum_valid, normalized}`; NIP `{checksum_valid, normalized}`; bank
`{format: IBAN|NRB, mod97_valid, normalized}`; address `{has_street, postal_code}`; date `{kind:
numeric|worded}`. Custom values are propagated via `RecognizerResult.recognition_metadata` (or attached
during DTO mapping).

---

## D8 — Model readiness: eager background load + `is_model_ready()` flag

**Decision**: At FastAPI startup (lifespan), kick off the model load **in a worker thread** (not on the
event loop). A module-level flag flips to ready on success and stays false on failure (logged, no crash).
`is_model_ready()` returns that flag. `health.check_spacy_model()` returns `"ok"`/`"unavailable"` from
the flag; `POST /v1/detect` raises **503** while not ready (FR-030).

**Rationale**: `/health` must answer in < 500 ms (Epic 1 SC-002) and must reflect *real* readiness
(FR-028) — an O(1) flag read does both, while an inference-based probe would blow the budget. Background
loading keeps `/health` reachable and the event loop responsive during the multi-second load; the Epic 1
container `HEALTHCHECK --start-period=30s` already absorbs this window. A load failure degrades health and
503s detect rather than crashing the process (graceful degradation, consistent with Epic 1's resilience
posture).

**Alternatives**: Lazy load on first `/v1/detect` (rejected — `/health` could not report readiness before
the first detect, violating FR-028); blocking synchronous startup load (rejected — would delay
`/health` availability and the socket bind).

---

## Polish identifier checksum algorithms (for `checksums.py`)

Normalize first (strip spaces/dashes) — offsets/returned text stay original (D, normalization.py).

- **PESEL** (11 digits `d0…d10`): weights `[1,3,7,9,1,3,7,9,1,3]`; `s = Σ d_i·w_i (i=0..9)`;
  `control = (10 − (s mod 10)) mod 10`; valid iff `control == d10`.
  **Gender**: `d9` even → female, odd → male. **Birth date**: `YY=d0d1`, `MM=d2d3`, `DD=d4d5`; the month
  encodes the century — `01–12`→1900s, `21–32`→2000s (post-2000 offset +20), `81–92`→1800s, `41–52`→2100s,
  `61–72`→2200s; subtract the offset to get the real month. An incoherent date lowers confidence but does
  not drop the match (FR-008 / edge case).
- **NIP** (10 digits `d0…d9`): weights `[6,5,7,2,3,4,5,6,7]`; `s = Σ d_i·w_i (i=0..8)`;
  `control = s mod 11`; **invalid if `control == 10`**; otherwise valid iff `control == d9`. **No
  non-zero-first-digit constraint** — a leading `0` is valid (FR-009).
- **REGON-9** (9 digits): weights `[8,9,2,3,4,5,6,7]`; `s` over first 8; `c = s mod 11`; if `c == 10` → `0`;
  valid iff `c == d8`.
- **REGON-14** (14 digits): weights `[2,4,8,5,0,9,7,3,6,1,2,4,8]`; `s` over first 13; `c = s mod 11`;
  if `c == 10` → `0`; valid iff `c == d13`. (The leading 9 digits are themselves a REGON-9; the 14-digit
  span wins overlap resolution — D4.)
- **Bank account NRB/IBAN** (26 digits, optional `PL` prefix, optional spaces): ISO 7064 **mod-97** — form
  `<26 digits> + "2521" + "00"` (P=25, L=21), interpret as an integer, valid iff `mod 97 == 1`.
  `format` metadata = `IBAN` when a `PL` prefix is present, else `NRB`. A bare 26-digit run with no
  banking context still surfaces at low confidence (recall-first).

References: official PESEL/NIP/REGON specifications (GUS) and ISO 13616 / ISO 7064 for IBAN.

---

## Polish date & address recognition

- **Polish dates** (`date_pl.py`, entity `DATE_TIME`): numeric `DD.MM.YYYY` / `DD-MM-YYYY` (and `D.M.YYYY`),
  plus worded — day + Polish month name in the **genitive** inflected form (`stycznia, lutego, marca,
  kwietnia, maja, czerwca, lipca, sierpnia, września, października, listopada, grudnia`) + year, with an
  optional trailing `r.` marker (`12 stycznia 2024 r.`). The stock Presidio `DateRecognizer` is
  English-oriented and insufficient (Constitution VI). `kind` metadata = `numeric|worded`.
- **Polish addresses** (`address.py`, entity `POLISH_ADDRESS`): street prefix (`ul.`, `al.`, `pl.`, `os.`)
  + name + building/flat number, postal code `XX-XXX`, city; single- or multi-line. Detected even with
  only postal code + city (no street) at a lower base score (`has_street: false`). A street that is a
  surname (`ul. Kowalskiego`) is part of the address — the overlap pass (D4) prevents a duplicate PERSON,
  and the address span subsumes any contained city LOCATION (no duplicate LOCATION).

---

## Phone numbers (PL region)

**Decision**: Configure Presidio's `PhoneRecognizer` with `supported_regions=["PL"]` (uses the
`phonenumbers` library, pulled in by `presidio-analyzer`). Covers national 9-digit numbers with optional
`+48`/`0048` prefix and optional spaces/dashes, mobile and landline. Context words: `tel`, `telefon`,
`kom`, `nr`.

---

## Known limitations (Constitution IX — documented, not solved)

- **Worded-date coverage gaps**: only the common day-month(genitive)-year pattern with optional `r.`;
  ranges, relative dates ("wczoraj"), and uninflected month names are out of scope this epic.
- **`pl_core_news_lg` NER weakness**: rare or foreign-origin person/place names, and names in oblique
  grammatical cases, may be missed or mis-typed; this is a model limitation, not a code defect.
- **Over-detection accepted by design**: low default thresholds mean random digit strings that pass a
  checksum, or 26-digit runs in non-banking text, are surfaced (recall over precision); false positives
  are expected and left for human review.
- **No formal evaluation**: precision/recall/F1 against a gold standard is Epic 8, out of scope here.

These are recorded in the gateway-api README/docs and linked from [quickstart.md](quickstart.md).
