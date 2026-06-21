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

## Anonymization pipeline & first LLM round-trip (Epic 4)

`gateway_api/pipeline/` orchestrates inbound pseudonymize → LLM → outbound de-pseudonymize, reusing
Epic 2 detection and the Epic 3 store. `POST /v1/chat/completions` (OpenAI-compatible in shape)
pseudonymizes **every** message each turn (so no original reaches the LLM), calls one provider behind
the `gateway_api/llm_providers/` port (a local **Ollama** REST adapter + a network-free echo stub),
then restores the originals in the answer. The outbound restore adds a bounded, PERSON/LOCATION-only
**fuzzy fallback** (`pseudonym_vault/fuzzy_restoration.py`) after the exact + inflection pass.

Config: `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT` (seconds; an exceeded call → **504**). Set `DEFAULT_MODEL`
to an **installed Ollama model** for the live demo — this epic talks to Ollama directly and does not
consult `DEFAULT_LLM_PROVIDER` (the provider router is a later epic). Errors: empty messages / a
non-user last message → **400**; Ollama unreachable or missing model → **503**; timeout → **504**;
every error preserves the `session_id`.

### Known limitations (Constitution IX — documented, not solved)

- **Fuzzy restores the base (nominative) form**: when an LLM inflects a fake PERSON/LOCATION in a form
  the suffix table did not foresee, the original is restored in its base form — identity is correct
  even if the surrounding grammar is slightly off. It is strictly PERSON/LOCATION only and prefix- and
  edit-distance-bounded, so identifiers/e-mail/phone are never fuzzed and invented names are not
  restored.
- **Synchronous only**: the full LLM answer is received before de-pseudonymization (no streaming).

## Frontend-ready surface, logging/metrics & session management (Epic 6)

The HTTP surface is hardened into the complete backend contract the React SPA is built against — no
new anonymization logic, the Epic 4/5 flow is reused unchanged (only the provider port now returns a
finish reason and the pipeline now returns timing/entity metrics).

- **`POST /v1/chat/completions`** returns the full OpenAI-shaped body — `id` (`chatcmpl-…`), `object`,
  `created`, the resolved `model`, and `choices[0]` with a **real** `finish_reason` normalized to
  `stop`/`length` — plus the gateway extensions: `anonymization_meta` (per-type `entities_detected`
  over the whole history, `total_entities`, `provider`, `model`, `processing_time_ms`, and the
  per-stage `timing_ms`) and `input_anonymization` (the latest user message's synthetic text +
  `replacements` with offsets into the original). Validation (empty messages, bad role/content,
  non-user last turn, unknown model) returns **400**; provider failures map to 503/429/504; **every**
  error body preserves `session_id`.
- **`GET` / `DELETE /v1/sessions/{id}`** — per-session dashboard statistics (`created_at`,
  `last_activity`, `ttl_remaining_seconds`, `entity_count`, `entities_by_type`, `message_count`) and
  session reset. 404 for a non-existent, TTL-expired, or never-stored (no PII) session. No auth: anyone
  holding a `session_id` may read/delete it (documented prototype limitation).
- **`GET /v1/providers`** — read-only `{name, requires_key, key_configured}` for openai/anthropic/ollama
  so the config panel can warn about a missing key before the first message. Never returns a key value;
  gate-exempt (answers while Redis is down).
- **Structured request log** — a separate, outermost middleware (`gateway_api/observability/`) emits
  **exactly one** JSON line per request to **stdout**: `timestamp`, `session_id`, `endpoint` (the route
  **template** — no path-parameter values), `provider`, `model`, `entities_detected`, and `timing_ms`
  (`ner_analysis`, `fake_generation`, `redis_write`, `llm_request`, `deanonymization`, `total`). It
  carries **no** original PII, message content, or fake values (Constitution VIII); a logging failure is
  caught (reported to stderr) and never breaks the request.

### Known limitations (Constitution IX — documented, not solved)

- **No authentication on any endpoint**: a thesis prototype; anyone with a `session_id` may GET/DELETE
  it, and there is no rate limiting or per-client isolation.
- **`message_count` requires session state**: it lives in the session metadata, which exists only once
  PII has been detected; a session whose only activity was PII-free turns has no stored state (404), so
  those successful turns are not separately counted.
- **`timing_ms` is wall-clock at instrumented boundaries**: `fake_generation` is derived
  (inbound substitution time − inbound Redis-write time), so a little inbound read time folds into it;
  the stages are for the dashboard, not a precise profiler.
