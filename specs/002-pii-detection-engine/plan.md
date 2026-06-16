# Implementation Plan: EPIC 2 — PII Detection Engine for Polish Civil-Law Contracts

**Branch**: `im/02-pii-detection-engine` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-pii-detection-engine/spec.md`

## Summary

Add a Polish-only **PII detection layer** to the existing `gateway-api` backend (Epic 1 runtime). Given a text string, a single `DetectionEngine.detect(text) -> list[DetectedEntity]` returns the personal data found in it — type, character offsets into the original text, an explainable confidence score, the exact matched substring, and type-specific metadata (PESEL gender, REGON variant, …). It detects only; it never substitutes, stores, or calls an LLM.

The engine is built on **Microsoft Presidio** with a **spaCy** NLP engine backed by **`pl_core_news_lg`** (already baked into the backend image in Epic 1). Presidio's base recognizers cover PERSON / LOCATION / EMAIL_ADDRESS / PHONE_NUMBER (phone configured for the PL region); everything Poland-specific (PESEL, NIP, REGON, bank account, postal address, Polish dates) is a **custom recognizer in its own module**. Scoring is deterministic and explainable: a fixed base pattern score, adjusted by checksum validation, plus a fixed context bonus from the `LemmaContextAwareEnhancer` when a label is nearby — yielding documented score bands the thesis can describe as a method. Per-entity-type minimum thresholds live in a **YAML file read live** (re-read on change, no restart) and are applied as a **post-filter** after analysis; defaults are deliberately low (recall over precision).

Two integration points touch Epic 1: a thin **`POST /v1/detect`** debug endpoint over the engine, and a **real `spacy_model` readiness check** in the existing `/health` surface (Epic 1 left a stub). Per the spec's clarifications, the detect route is **exempt from the Epic 1 Redis gate** (detection is stateless) and is **gated on model readiness** instead (HTTP 503 when the model is not loaded — no partial results). No PII ever reaches logs.

## Technical Context

**Language/Version**: Python 3.12 (backend `apps/gateway-api`); no frontend work in this epic.

**Primary Dependencies**: FastAPI + uvicorn (existing); **`presidio-analyzer`** (new); **spaCy** + **`pl_core_news_lg`** (spaCy already a dep; model baked into the image at Dockerfile line 38); **`pyyaml`** (new, for the threshold file); `phonenumbers` (pulled in by presidio-analyzer, used by the PL phone recognizer). Package manager: `uv` via `@nxlv/python`. Tests: `pytest` (existing config).

**Storage**: None for this epic. Detection is stateless — no Redis, no session, no persistence (Epic 3 introduces the encrypted mapping store). The threshold YAML is read-only configuration, not data.

**Testing**: `pytest` per `apps/gateway-api/tests/` (run via `nx run gateway-api:test` → `uv run pytest tests/`). Recognizer/checksum unit tests require **no model**; engine/API integration tests require `pl_core_news_lg` (skip-if-absent guard for environments without it; CI/image have it baked).

**Target Platform**: Linux container (Docker Compose) and native macOS/Linux dev (uvicorn). Same as Epic 1.

**Project Type**: Web-service backend within an Nx integrated monorepo; the detection layer is a self-contained Python package under `gateway_api/detection/` with one thin FastAPI route.

**Performance Goals**: No detection latency/throughput SLA in this epic (spec: out of scope). Hard constraint preserved from Epic 1: `GET /health` < 500 ms — satisfied because the model-readiness check is an O(1) flag read, never an inference. Model load is heavy and happens **once** (eager background load at startup), never per request.

**Constraints**: Polish only (no language switch, no English model). No PII or matched values in logs — only entity types, counts, scores, timings (Constitution VIII). Deterministic scoring (identical input + config → identical output). Offsets/returned text always reference the original input exactly, including separators. Synchronous request/response only.

**Scale/Scope**: Thesis/demo scale, single host. Six custom recognizers + four configured base recognizers, one DTO, one engine, one YAML config, one debug endpoint, one health-check change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0. This is the first epic that exercises the detection principles directly.

| Principle | Applicability to Epic 2 | Status |
|-----------|-------------------------|--------|
| I. Privacy by Design | Detection only; nothing leaves the system. The debug endpoint involves no LLM and no outbound traffic. No bypass introduced. | ✅ Pass |
| II. Recall over Precision | Default per-type thresholds are deliberately low; bad-checksum values are surfaced at low confidence (not dropped); threshold 0 = "paranoid". Central design driver. | ✅ Pass |
| III. Reversibility within Session | N/A — no mapping/substitution/storage this epic. The detect path is deliberately Redis-free (spec clarification). | ✅ N/A |
| IV. Provider Agnosticism | No LLM provider touched. | ✅ N/A |
| V. Synchronous Only | `detect()` and `POST /v1/detect` are synchronous request/response. | ✅ Pass |
| VI. Polish First | spaCy `pl_core_news_lg` + custom Polish recognizers (PESEL/NIP/REGON/NRB/address/PL dates) as core. No English path. | ✅ Pass |
| VII. Realistic Substitution | N/A — no substitution this epic. | ✅ N/A |
| VIII. No PII in Logs | Engine and endpoint log only entity types, counts, scores, timings — never the input text or matched values. Enforced as a design requirement and a test. | ✅ Pass |
| IX. Simplicity over Completeness | Known limitations documented (worded-date coverage gaps; `pl_core_news_lg` weakness on rare/foreign names; over-detection accepted by design). Formal P/R/F1 deferred to Epic 8. | ✅ Pass |

**Technology Constraints**: Python 3.12 + FastAPI ✅; **Presidio + spaCy `pl_core_news_lg`** ✅ (exactly the mandated NER stack); Faker/Redis not used this epic (not yet needed) ✅; no provider coupling ✅. New libraries (`presidio-analyzer`, `pyyaml`) are additive within the mandated stack — **no deviations**.

**Gate result: PASS.** Complexity Tracking is empty. Two design choices refine the user's suggested Presidio API usage for correctness — both documented with rationale in [research.md](research.md) (D3 checksum scoring, D4 overlap resolution); neither is a constitution deviation.

## Project Structure

### Documentation (this feature)

```text
specs/002-pii-detection-engine/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature spec (+ Clarifications session 2026-06-16)
├── research.md          # Phase 0 — decisions: Presidio/spaCy PL wiring, scoring, checksums, overlap
├── data-model.md        # Phase 1 — DetectedEntity DTO, metadata schemas, threshold config, score bands
├── quickstart.md        # Phase 1 — validation guide (native + container)
├── contracts/           # Phase 1
│   ├── detect.openapi.yaml      # POST /v1/detect + DetectedEntity schema + 503-when-model-down
│   ├── recognizers.md           # per-recognizer contract (entity type, match intent, context, checksum, metadata)
│   ├── thresholds.md            # threshold YAML schema, defaults (F-10), live-reload semantics
│   └── health-readiness.md      # spacy_model readiness delta to the Epic 1 /health contract
├── checklists/
│   └── requirements.md  # spec quality checklist (16/16)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

New code is additive inside the existing `gateway-api` app; **bold** = new, *italic* = modified.

```text
apps/gateway-api/
├── pyproject.toml                         # *add presidio-analyzer, pyyaml*
├── Dockerfile                             # (unchanged — pl_core_news_lg already baked at L38)
├── gateway_api/
│   ├── main.py                            # *exempt /v1/detect from Redis gate (FR-031); register detect router + lifespan model load*
│   ├── config.py                          # *add DETECTION_THRESHOLDS_PATH setting (optional, with default)*
│   ├── health.py                          # *check_spacy_model() → real readiness flag (FR-028)*
│   ├── dependencies.py                    # (unchanged)
│   ├── detection/                         # ── new detection package ──
│   │   ├── __init__.py                    # exports DetectionEngine, DetectedEntity
│   │   ├── dto.py                         # **DetectedEntity (pydantic model)**
│   │   ├── nlp.py                         # **spaCy NlpEngine provider + PL label mapping + lazy singleton + is_model_ready()**
│   │   ├── engine.py                      # **DetectionEngine: AnalyzerEngine wiring, DTO mapping, overlap pass, threshold post-filter**
│   │   ├── scoring.py                     # **score constants/bands + final clamp to [0, 0.99]**
│   │   ├── thresholds.py                  # **YAML loader with mtime-based live reload + post-filter**
│   │   ├── normalization.py               # **strip separators for validation while preserving original span**
│   │   ├── checksums.py                   # **pure functions: PESEL/NIP/REGON-9/REGON-14/mod-97 + gender/birth-date derivation**
│   │   ├── default_thresholds.yaml        # **shipped defaults (F-10)**
│   │   └── recognizers/
│   │       ├── __init__.py                # registry assembly (custom + configured base recognizers)
│   │       ├── _checksum_base.py          # **ChecksumPatternRecognizer base (explicit score bands; see research D3)**
│   │       ├── pesel.py                   # **PeselRecognizer**
│   │       ├── nip.py                     # **NipRecognizer**
│   │       ├── regon.py                   # **RegonRecognizer (9 & 14)**
│   │       ├── bank_account.py            # **PolishBankAccountRecognizer (NRB/IBAN)**
│   │       ├── address.py                 # **PolishAddressRecognizer**
│   │       └── date_pl.py                 # **Polish DateRecognizer (numeric + worded)**
│   └── api/
│       ├── __init__.py
│       └── detect.py                      # **POST /v1/detect router (thin; model-readiness 503 dependency)**
└── tests/
    ├── conftest.py                        # *add detection fixtures (engine, model-ready monkeypatch, tmp threshold file)*
    ├── test_health.py                     # *extend: spacy_model real readiness ok/unavailable*
    ├── test_detect_api.py                 # **endpoint: shape, empty input, model-down 503, redis-down still serves, no-PII-in-logs**
    └── detection/
        ├── test_checksums.py              # **pure checksum/gender/date unit tests**
        ├── test_pesel.py  test_nip.py  test_regon.py
        ├── test_bank_account.py  test_address.py  test_date_pl.py
        ├── test_scoring.py                # **bands: valid/invalid × labelled/unlabelled, clamp**
        ├── test_thresholds.py             # **post-filter, paranoid=0, disable=1, live reload**
        └── test_engine.py                 # **DTO mapping, offsets/normalization, overlap (NIP⊂PESEL, REGON9⊂14, ADDRESS⊃LOCATION)**
```

**Structure Decision**: Keep the detection layer as a cohesive `gateway_api/detection/` package (one module per recognizer, pure checksum logic isolated in `checksums.py` for fast model-free unit tests), with a single thin FastAPI route under `gateway_api/api/`. No shared `libs/` is introduced — the engine is internal to `gateway-api` and exposed only via `DetectionEngine.detect()` and `POST /v1/detect`. This matches Epic 1's "no shared libs yet" decision and keeps the engine independently unit-testable per the spec's quality bar.

## Implementation Phases

These phases drive the eventual `tasks.md` (`/speckit-tasks`). Each is independently verifiable; later phases depend on earlier ones.

- **Phase 0 — Dependencies & NLP engine**: add `presidio-analyzer` + `pyyaml` to `pyproject.toml`, `uv lock`/`sync`; build `detection/nlp.py` — `NlpEngineProvider` spaCy config for `pl` with the **NKJP→Presidio label mapping** (`persName`→PERSON, `placeName`/`geogName`→LOCATION, `date`/`time`→DATE_TIME), a process-singleton model loader, and `is_model_ready()`. *Verify*: a tiny script/test loads the engine and `analyze("Jan Kowalski mieszka w Warszawie", language="pl")` yields PERSON + LOCATION.
- **Phase 1 — Checksums & normalization (pure, model-free)**: `checksums.py` (PESEL control sum + gender + birth-date/century; NIP; REGON-9; REGON-14; IBAN/NRB mod-97) and `normalization.py` (strip spaces/dashes, keep original span). *Verify*: `test_checksums.py` green — positive, bad-checksum, post-2000 PESEL, NIP leading-zero, REGON 9 vs 14.
- **Phase 2 — DTO, scoring & thresholds**: `dto.py` (`DetectedEntity`), `scoring.py` (band constants + clamp to ≤0.99), `thresholds.py` (load `default_thresholds.yaml`, env override path, mtime live-reload, post-filter). *Verify*: `test_scoring.py`, `test_thresholds.py` — bands, paranoid=0, disable=1, reload without restart.
- **Phase 3 — Custom recognizers**: `_checksum_base.py` (explicit-band `ChecksumPatternRecognizer`, research D3) then `pesel/nip/regon/bank_account/address/date_pl.py`, each declaring context words for the enhancer. *Verify*: per-recognizer test modules (positive/negative/edge: separators, labelled vs unlabelled, IBAN vs continuous NRB, address without street).
- **Phase 4 — Engine assembly**: `recognizers/__init__.py` registry (custom + base PERSON/LOCATION/EMAIL/PHONE-PL) and `engine.py` — `AnalyzerEngine` with the custom `LemmaContextAwareEnhancer`, map `RecognizerResult`→`DetectedEntity`, attach metadata, **deterministic overlap-resolution pass** (longest/containing wins; ADDRESS subsumes contained LOCATION — research D4), then threshold post-filter. *Verify*: `test_engine.py` — offsets/normalization, NIP⊂PESEL, REGON-9⊂REGON-14, city⊂address, empty input → `[]`.
- **Phase 5 — API & health wiring**: `api/detect.py` (`POST /v1/detect`, thin, 503 via model-readiness dependency — FR-030); `main.py` (lifespan eager background model load; add `/v1/detect` to the Redis-gate exemption — FR-031); `health.py` (`check_spacy_model()` → `is_model_ready()`). *Verify*: `test_detect_api.py` + extended `test_health.py` — `/health` reports `spacy_model` real status; `/v1/detect` 503 when model down, still served when Redis down; logs carry no PII.
- **Phase 6 — Limitations doc**: record Constitution-IX limitations (worded-date gaps, rare/foreign-name weakness, over-detection by design) in the gateway-api README / docs and link from `quickstart.md`.

## Key Technical Decisions

Full decision + rationale + alternatives in [research.md](research.md). Summary:

| Decision | Rationale |
|---|---|
| Build on Presidio `AnalyzerEngine` + spaCy `pl_core_news_lg`, model loaded once as a process singleton | Mandated NER stack (Constitution); model load is heavy and must not recur per request. (research D1) |
| Configure NKJP→Presidio label mapping in the NlpEngine | `pl_core_news_lg` emits `persName`/`placeName`/`geogName`/`date`, **not** English labels; without remapping PERSON/LOCATION are missed. (research D2) |
| **Checksum scoring via explicit score bands, not `validate_result` True/False** | Presidio drops a result when `validate_result` returns `False` (score→MIN, filtered). FR-014 requires bad-checksum kept at low confidence. A `ChecksumPatternRecognizer` assigns valid/invalid bands explicitly and keeps both. (research D3) |
| **Deterministic overlap-resolution pass in the engine, not anonymizer `ConflictResolutionStrategy`** | `ConflictResolutionStrategy.MERGE_SIMILAR_OR_CONTAINED` is an *anonymizer* concept and merges only same-type spans. Cross-type containment (NIP⊂PESEL, ADDRESS⊃LOCATION) needs an explicit longest-span-wins pass. (research D4) |
| Per-type thresholds as a **post-filter** from a live YAML file | `AnalyzerEngine.analyze()` takes only one global `score_threshold`; per-type minimums + no-restart reload are met by a post-analysis filter reading a YAML file (mtime reload). No Redis (keeps detect path stateless). (research D5) |
| Final score **clamped to ≤ 0.99** | Reserves 1.0 so a threshold of `1.0` is a true "disable this type" (FR-022); also gives clean "valid+labelled ≈ 0.99" band. (research D6) |
| Context bonus via `LemmaContextAwareEnhancer` with `min_score_with_context_similarity=0.0` | Disables the default 0.4 floor so a label near a **bad-checksum** value raises it only modestly (stays low), keeping the bands monotonic and explainable. (research D6) |
| Project DTO `DetectedEntity` at the engine boundary (not raw `RecognizerResult`) | Stable contract for later epics; carries `metadata` dict (gender, REGON variant, normalized value) that `RecognizerResult` has no native slot for. (research D7) |
| Eager **background** model load at FastAPI startup + `is_model_ready()` flag | Lets `/health` report real readiness within its 500 ms budget (O(1) flag read) and `/v1/detect` 503 until ready, without blocking startup or the event loop. (research D8) |

## Complexity Tracking

> No constitution violations. Section intentionally empty.
