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

## Substitution & reversible mapping (Epic 3)

Realistic Polish fakes (`gateway_api/pseudonym_generation/`, Faker `pl_PL`) + a reversible,
AES-256-GCM-encrypted session store (`gateway_api/pseudonym_vault/`, one Redis HASH per session,
sliding 30-min TTL). Debug surface (no LLM): `POST /v1/pseudonymize`, `POST /v1/depseudonymize`,
`GET /v1/sessions/{id}/mappings`. Only original PII is encrypted; synthetic fakes are stored in
clear as the reverse index and forward field names are a keyed HMAC (Constitution v1.1.0).

### Known limitations (Constitution IX — documented, not solved)

- **No name ↔ PESEL gender association**: a fake person's gender is chosen at random; it is not
  tied to a nearby PESEL's gender. (A fake PESEL *does* preserve the gender of the PESEL it
  replaces — only the PERSON name is independent.)
- **No cross-field date-of-birth coherence**: a fake date is shifted ±10 years independently of
  any PESEL-encoded birth date; the two are not kept consistent with each other.
- **Inflection covers common patterns only**: adjectival `-ski/-ska`, consonant-ending masculine
  (incl. fleeting-e and k/g softening), `-a`-ending feminine, and common city patterns. Rare,
  foreign, or indeclinable names fall back to the base form. Soft-consonant and multi-word/hyphenated
  city names (e.g. "Stalowa Wola", "Skarżysko-Kamienna") inflect approximately. Restoration is always
  literal (the exact original surface is captured per occurrence), so reversibility holds regardless.
- **Foreign / diacritic names** (e.g. "Müller", "Nguyen", "François"): detected and reversible, but
  cross-case **consistency depends on spaCy lemmatisation**, which usually does not reduce a foreign
  oblique form to its base — so the same foreign person seen in different cases may receive different
  fakes, and an oblique foreign name is occasionally mistyped (e.g. PERSON vs LOCATION). Rare *Polish*
  surnames (e.g. "Brzęczyszczykiewicz") work well — they follow the consonant-ending pattern.
- **Hyphenated / double-barrelled surnames** (e.g. "Kowalczyk-Wąsowicz"): spaCy detects them
  inconsistently (whole token in one place, split parts in another), which the whole-name coreference
  cannot bridge; substitution of such a name can be inconsistent and may not round-trip cleanly. A
  detection/tokenisation limitation surfaced at the Epic 2 boundary.
- **Addresses are atomic**: a postal address is replaced and restored as one block and is never
  internally inflected; only standalone cities (LOCATION) are case-inflected.
- **Redis restart loses the session**: durability is out of scope — a restart drops all mappings;
  starting a new session is the expected recovery.
