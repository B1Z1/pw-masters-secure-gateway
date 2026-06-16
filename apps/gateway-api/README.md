# gateway-api

Backend API for the LLM anonymization gateway.

## PII detection (Epic 2)

A Polish-only PII **detection** layer built on Microsoft Presidio + spaCy
`pl_core_news_lg`. Given text, `DetectionEngine.detect()` (and `POST /v1/detect`)
returns detected entities — type, character offsets, an explainable confidence
score, the exact matched text, and metadata. Detection only: nothing is
substituted, stored, logged, or sent to an LLM (later epics).

- Entity types: `PERSON`, `LOCATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `DATE_TIME`,
  `PESEL`, `NIP`, `REGON`, `POLISH_BANK_ACCOUNT`, `POLISH_ADDRESS`.
- Per-type confidence thresholds live in `gateway_api/detection/default_thresholds.yaml`
  (override via `DETECTION_THRESHOLDS_PATH`), read live — edits apply on the next
  request, no restart. Defaults are deliberately low (recall over precision).
- `/health` reports real `spacy_model` readiness; `POST /v1/detect` returns 503 while
  the model is not loaded and is exempt from the Redis-availability gate.
- See `specs/002-pii-detection-engine/` for the spec, plan, contracts, and quickstart.

### Known limitations (Constitution IX — documented, not solved)

- **Worded-date coverage**: only the common `day month(genitive) year` pattern with an
  optional `r.` marker. Date ranges, relative dates ("wczoraj"), and uninflected month
  names are out of scope this epic.
- **`pl_core_news_lg` NER weakness**: rare or foreign-origin person/place names, and
  names in oblique grammatical cases, may be missed or mis-typed — a model limitation,
  not a code defect. When the spaCy `date` span and the custom `DateRecognizer` overlap,
  the longer span wins, so a model-provided `DATE_TIME` may omit the custom `kind` metadata.
- **Over-detection accepted by design**: low default thresholds surface borderline values
  (a random digit string that happens to pass a checksum, a 26-digit run in non-banking
  text). False positives are expected and left for human review.
- **PESEL/REGON with separators**: matched in their contiguous (unseparated) form; NIP and
  bank-account separators (dashes/spaces) are handled. Separated PESEL/REGON are rare in
  practice and not specially matched.
- **No formal evaluation**: precision/recall/F1 against a gold standard is Epic 8.
- **`tldextract` network probe**: Presidio's email recognizer may attempt a one-time TLD
  public-suffix-list fetch; in an offline/egress-restricted environment it falls back to a
  bundled snapshot (non-fatal).
