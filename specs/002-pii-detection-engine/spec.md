# Feature Specification: EPIC 2 — PII Detection Engine for Polish Civil-Law Contracts

**Feature Branch**: `im/02-pii-detection-engine`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "EPIC 2 — PII Detection Engine for Polish civil-law contracts. Build an independent detection layer that takes a Polish text string and returns a list of detected personally identifiable information (PII) entities. Each entity reports its type, its character position in the original text (start/end), a confidence score, the matched text exactly as it appears in the input, and — for some types — extra metadata. This layer performs detection ONLY: it does not substitute, mask, store, or send anything anywhere. It must be exercisable in isolation from the rest of the system. The language is Polish only."

## Overview

This epic delivers the detection layer of the anonymization gateway: given a Polish text string, it
returns the personal data found inside it. It is a pure read-over-text capability — it **detects and
describes**, it does not substitute, mask, store, persist, or transmit anything. Substitution,
reversible mapping, and LLM proxying are later epics; this layer is the input to them and must be
usable entirely on its own.

The engine recognises free-text personal data (names, places, e-mails, phone numbers, dates) and
Poland-specific structured identifiers and financial data (PESEL, NIP, REGON, bank account numbers,
postal addresses), the latter with both format **and** checksum validation. Every detection carries an
explainable confidence score, and detection is tuned to favour **recall over precision**: in a legal
context it is safer to over-detect and let a human discard false positives than to miss real personal
data.

Two operational touch-points are added: a lightweight **debug surface** that lets a reviewer submit
text and see exactly what the engine catches (no LLM, no substitution), and an extension of the
**existing health surface** so it reports whether the underlying Polish language model is actually
loaded and ready — degrading when it is not. The health endpoint, its aggregation rule, and its
response schema (delivered in EPIC 1) are reused unchanged; only the model-readiness check is made
real (it was a stub returning "ok").

## Clarifications

### Session 2026-06-16

- Q: When the Polish language model (NER) is unavailable, how should the detection/debug endpoint respond? → A: Return HTTP 503 and refuse the request — it does NOT return partial, regex/checksum-only results. (The `/health` endpoint separately continues to report `degraded`; the two behaviours are independent.)
- Q: Is the stateless detection/debug endpoint subject to the EPIC 1 Redis-availability gate (which 503s every non-health route when Redis is down)? → A: No — exempt it from the Redis gate (detection has no Redis dependency); gate it only on model availability. The exemption is added in the EPIC 1 middleware alongside `/health`.
- Q: Where do the per-type confidence thresholds live, and how is "takes effect without restart" achieved given EPIC 1's cached env-based settings? → A: In a dedicated threshold configuration file (YAML/JSON), separate from the env-based `Settings` (which stays cached for secrets/startup config), read live (per request or on file-change) so an edit applies on the next detection request without a restart. No Redis dependency (consistent with the detection path being Redis-free). Exact format and read strategy are a plan detail.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect personal data in Polish text and inspect the results (Priority: P1)

A thesis reviewer (or a developer) submits a piece of Polish text to the engine and receives back a
complete list of the personal data it contains. For each item they see what kind of data it is, where
it sits in the text (start and end character positions), how confident the engine is, the exact text
that was matched, and — where applicable — extra details. Nothing in the submitted text is altered,
stored, or forwarded anywhere; the reviewer is simply shown what was found.

**Why this priority**: This is the headline deliverable and the only way the engine is exercised and
evaluated in this epic. It is the minimum viable slice: a self-contained "give me text, get back
entities" capability that proves the engine works end to end and can be demonstrated without any other
part of the system.

**Independent Test**: Submit several representative Polish snippets (containing names, an e-mail, a
phone number, a date, and at least one structured identifier) to the debug surface and confirm the
returned list reports the correct type, character offsets, score, exact matched text, and metadata for
each — and that an empty input returns an empty list with no error.

**Acceptance Scenarios**:

1. **Given** a Polish sentence containing a person's name, an e-mail address, and a phone number,
   **When** the text is submitted for detection, **Then** the engine returns one entity per item, each
   with its type, start/end offsets into the original text, a confidence score, and the exact matched
   substring.
2. **Given** the engine returns an entity, **When** the matched substring is read back using the
   reported start/end offsets against the original input, **Then** it is byte-for-byte identical to the
   reported matched text.
3. **Given** an empty string (or whitespace only), **When** it is submitted, **Then** the engine
   returns an empty entity list and does not raise an error.
4. **Given** any submitted text, **When** detection runs, **Then** the submitted text and the matched
   values are never written to logs, persisted, substituted, or sent to any external service — only the
   detection result is returned to the caller.
5. **Given** a Polish date written in words ("12 stycznia 2024 r.") and a numeric date ("12.01.2024"),
   **When** the text is submitted, **Then** both are returned as date entities.

---

### User Story 2 - Validate Polish national identifiers and financial data with checksums and metadata (Priority: P2)

A reviewer submits text containing Polish structured identifiers — PESEL, NIP, REGON, bank account
numbers, postal addresses — possibly written with spaces or dashes. The engine recognises each by
format, validates it against its official checksum where one exists, and reports useful derived details
as metadata: the gender encoded in a PESEL, which REGON variant (9- or 14-digit) matched, and so on.
Whether or not a value passes its checksum, it is surfaced; passing values are reported with higher
confidence than failing ones.

**Why this priority**: Validated, metadata-rich recognition of Polish identifiers is the distinctive
contribution of the detection layer over generic, language-only name/place recognition, and it is what
the thesis evaluates most closely. It builds on the engine and debug surface from US1.

**Independent Test**: Feed known-valid and known-invalid PESEL/NIP/REGON/bank-account values (in
labelled and unlabelled, separated and unseparated forms) and confirm each is detected, that valid ones
score higher than invalid ones, that the reported text/offsets point at the original separated form,
and that metadata (PESEL gender, REGON variant) is correct.

**Acceptance Scenarios**:

1. **Given** a valid 11-digit PESEL, **When** it is detected, **Then** its control sum is reported as
   passing, the gender is derived from the relevant digit (even = female, odd = male) and returned as
   metadata, and the birth date is interpreted with the correct century (post-2000 dates apply the
   month offset).
2. **Given** a PESEL with an invalid control sum, **When** it is detected, **Then** it is still returned
   (format matched) but with low confidence rather than dropped.
3. **Given** a valid NIP that begins with the digit 0, **When** it is detected, **Then** it is accepted
   as valid — the format does not require a non-zero first digit.
4. **Given** a 9-digit REGON and a 14-digit REGON that begins with that same 9-digit prefix, **When**
   they are detected, **Then** each variant validates against its own control sum and metadata reports
   which variant matched; where the 14-digit value contains the 9-digit value, the longer value is the
   one returned (see US4).
5. **Given** a Polish bank account written as an IBAN with a "PL" prefix and spaces, and the same number
   written as a continuous 26-digit run, **When** each is detected, **Then** both forms are recognised
   and (optionally) validated via the mod-97 check.
6. **Given** any of the above written with spaces or dashes, **When** it is detected, **Then**
   validation is performed on the value with separators stripped, but the returned matched text and
   offsets point at the original span exactly as written, separators included.
7. **Given** a postal address (street + building/flat number, postal code in XX-XXX form, city), and
   separately an address with only a postal code and city (no street), **When** each is detected,
   **Then** both are returned as address entities, the street-less one at lower confidence.

---

### User Story 3 - Tune detection with explainable, configurable, recall-first scoring (Priority: P3)

An operator running the engine in a legal context wants to control how aggressively it flags personal
data, and the thesis author needs to describe the scoring as a consistent method rather than a set of
hand-picked numbers. Confidence is computed deterministically: it rises when a value passes its
checksum and when a recognisable context label sits next to it (e.g. "PESEL:", "NIP:", "nr rachunku"),
and falls when the checksum fails or no label is present. Each entity type has its own minimum
confidence threshold held in configuration; raising or lowering a threshold changes what is returned on
the next request without restarting the system. Defaults are deliberately low so the engine
over-detects and surfaces borderline cases for human review.

**Why this priority**: Configurable, explainable, recall-first scoring is what makes the engine
defensible academically and usable operationally, but it refines output that US1/US2 already produce,
so it ranks after them.

**Independent Test**: Submit the same text repeatedly while changing a type's threshold in
configuration; confirm scores are identical across runs for identical input (deterministic), that a
threshold of 0 surfaces every candidate of that type, that a threshold of 1 returns none of that type,
that the same value scores higher with an adjacent context label than without, and that a threshold
change takes effect on the next request without a restart.

**Acceptance Scenarios**:

1. **Given** identical input and identical configuration, **When** detection is run twice, **Then** the
   returned entities and their scores are exactly the same (deterministic, explainable scoring).
2. **Given** the same valid identifier written once with an adjacent context label and once without,
   **When** both are detected, **Then** the labelled occurrence has a higher confidence than the
   unlabelled one, and the unlabelled one is still detected.
3. **Given** a type's minimum confidence threshold set to 0, **When** detection runs, **Then** every
   candidate the recognizer surfaces for that type is returned ("paranoid" mode).
4. **Given** a type's minimum confidence threshold set to 1, **When** detection runs, **Then** that type
   is effectively disabled (no entities of that type are returned).
5. **Given** a threshold value is changed in configuration, **When** the next detection request is made,
   **Then** the new threshold is applied without restarting the system.
6. **Given** a value whose checksum fails, **When** it is detected, **Then** its confidence is lower than
   an otherwise-identical value whose checksum passes.

---

### User Story 4 - Resolve overlapping detections into a single best entity (Priority: P3)

When the recognizers produce candidate spans that overlap or nest inside one another — a 10-digit NIP
sitting inside an 11-digit PESEL, a city name inside a full postal address, a 9-digit REGON inside a
14-digit one, a street named after a surname inside an address — the engine returns one clean,
best-choice entity per region instead of several overlapping ones. The longer/containing span wins, and
contained or near-duplicate detections are merged.

**Why this priority**: A deduplicated, non-overlapping result is what makes the output usable by a
reviewer and by the later substitution epic, but it is a refinement of the raw candidate set from
US1/US2.

**Independent Test**: Feed inputs engineered to produce overlapping candidates (REGON-9 within REGON-14,
city within an address, "ul. Kowalskiego" as a street) and confirm a single containing entity is
returned for each region with no duplicate or contained leftovers.

**Acceptance Scenarios**:

1. **Given** two candidate spans where one fully contains the other, **When** overlaps are resolved,
   **Then** only the longer/containing span is returned.
2. **Given** a city name that falls inside a detected postal address, **When** overlaps are resolved,
   **Then** the address span subsumes the city and no separate place entity is returned for it.
3. **Given** an address whose street is a surname ("ul. Kowalskiego"), **When** it is detected, **Then**
   the surname is treated as part of the address and not returned as a separate person entity.
4. **Given** a first name and last name adjacent in the text, **When** they are detected, **Then**
   returning them as one person span OR as two adjacent person spans are both acceptable outcomes.

---

### User Story 5 - Reflect language-model readiness in the health surface (Priority: P3)

An operator or orchestration system queries the system's existing health surface to learn whether the
detection engine is actually able to work. Because detection depends on a Polish language model being
loaded into memory, the health surface reports whether that model is loaded and ready; if the model is
unavailable, the overall health degrades, exactly as it already does for other dependencies.

**Why this priority**: Operability and honest readiness reporting matter for running and demonstrating
the system, but they sit on top of the detection capability itself, so they come last. This replaces
the EPIC 1 placeholder that always reported the model as available.

**Independent Test**: Query the health surface with the model loaded (expect the model reported as
available and overall status "ok", all else healthy); make the model unavailable and query again
(expect the model reported as unavailable and overall status "degraded", with the HTTP behaviour
unchanged from EPIC 1).

**Acceptance Scenarios**:

1. **Given** the Polish language model is loaded and ready, **When** the health surface is queried,
   **Then** it reports the model as available and contributes "ok" to the overall status.
2. **Given** the Polish language model is not loaded or failed to load, **When** the health surface is
   queried, **Then** it reports the model as unavailable and the overall status is "degraded", while the
   endpoint still responds successfully (the EPIC 1 always-200 behaviour and response schema are
   unchanged).

---

### Edge Cases

- **Separators in identifiers** (PESEL/NIP/REGON/bank account with spaces or dashes): validation runs on
  the normalized value (separators stripped); the returned text and offsets keep the original separated
  form.
- **PESEL with an invalid control sum**: surfaced with low confidence (format matched, value probably
  not a real PESEL) rather than dropped.
- **A random 11-digit string that happens to satisfy the PESEL checksum**: accepted — over-detection is
  acceptable in this context.
- **Post-2000 PESEL birth dates**: the month digits are offset (by 20); the engine interprets the
  century correctly when deriving the birth date.
- **NIP starting with 0**: valid — the format must not require a non-zero first digit.
- **Identifier without any context label** (no "PESEL:"/"NIP:"/"REGON:"/"nr rachunku" nearby): detected,
  but at reduced confidence.
- **14-digit REGON that begins with the firm's 9-digit REGON**: the longer (14-digit) match wins.
- **Bank account as a PL-prefixed IBAN or a continuous 26-digit run**: both forms handled; a bare
  26-digit run in a clearly non-banking context is returned with low confidence.
- **Address with no street** (only postal code + city): detected, at lower confidence.
- **Address whose street is a surname** ("ul. Kowalskiego"): part of the address, not a separate person.
- **First + last name**: acceptable either as one person span or as two adjacent person spans.
- **City embedded inside a detected address**: subsumed by the address span; no duplicate place entity.
- **Threshold extremes**: 0 surfaces everything a recognizer produces ("paranoid" mode); 1 effectively
  disables the type.
- **Empty input**: returns an empty entity list without error.
- **Model not loaded**: the detection/debug endpoint rejects the request with HTTP 503 and does NOT
  return partial (regex/checksum-only) results, so a caller can never mistake a model-less scan for a
  complete one. Independently, the health surface reports degraded (see US5). (Clarified 2026-06-16.)
- **Redis unavailable**: the detection/debug endpoint still serves normally — detection has no Redis
  dependency, so this route is exempt from the EPIC 1 Redis-availability gate and is gated only on the
  model. (Clarified 2026-06-16.)

## Requirements *(mandatory)*

### Functional Requirements

#### Detection engine & entity output

- **FR-001**: The engine MUST accept a Polish text string and return an ordered list of detected PII
  entities; an empty or whitespace-only input MUST return an empty list with no error.
- **FR-002**: Each returned entity MUST report: its type, its start character offset, its end character
  offset, a confidence score (a number between 0 and 1 inclusive), the exact matched substring as it
  appears in the input, and — for types that support it — additional metadata.
- **FR-003**: The reported offsets and matched text MUST always reference the original input exactly
  (including any separators), even when validation or scoring operated on a normalized form of the
  value.
- **FR-004**: The engine MUST detect, at minimum, these entity types: person names, places/locations,
  e-mail addresses, phone numbers in Polish formats, dates expressed in Polish (numeric such as
  "12.01.2024" / "12-01-2024" and worded such as "12 stycznia 2024 r."), PESEL, NIP, REGON, Polish bank
  account numbers (NRB/IBAN), and Polish postal addresses.
- **FR-005**: The engine MUST operate for Polish only — there is no language switch and no English model
  or English-specific recognizers.
- **FR-006**: The engine MUST be exercisable in isolation: a single detection operation over a supplied
  text, with NO substitution, masking, storage, persistence, or transmission of the text or its detected
  values to any external service.
- **FR-007**: The engine MUST NOT write the submitted text or any matched value to logs; only metadata
  (entity types, counts, scores, timings, error categories) may be logged (Constitution VIII — No PII in
  Logs).

#### Polish identifiers & financial data (format + checksum validation, metadata)

- **FR-008**: The engine MUST detect 11-digit PESEL numbers, validate the PESEL control sum, derive the
  person's gender from the relevant digit (even = female, odd = male) and report it as metadata, and
  interpret the encoded birth date with the correct century, accounting for the post-2000 month offset.
- **FR-009**: The engine MUST detect 10-digit NIP numbers and validate the NIP control sum; it MUST
  accept a NIP whose first digit is 0 (no non-zero-first-digit requirement).
- **FR-010**: The engine MUST detect REGON numbers in both the 9-digit and 14-digit variants, validate
  each against its own control sum, and report which variant matched as metadata.
- **FR-011**: The engine MUST detect Polish bank account numbers in NRB/IBAN form (26 digits, optionally
  "PL"-prefixed, optionally spaced), handling both the continuous run and the prefixed/spaced forms, and
  MUST support optional validation via the mod-97 check.
- **FR-012**: The engine MUST detect Polish postal addresses composed of street + building/flat number,
  a postal code in XX-XXX form, and a city, across single or multiple lines; it MUST also detect an
  address that has only a postal code and city (no street), at lower confidence.
- **FR-013**: For any value that may contain separators (PESEL, NIP, REGON, bank account), validation
  MUST be performed on the normalized value (separators stripped) while the returned text and offsets
  continue to reference the original span exactly as written.
- **FR-014**: A value whose checksum FAILS (e.g. a malformed or fake PESEL/NIP/REGON/account) MUST still
  be surfaced (format matched) at reduced confidence rather than dropped; a value whose checksum PASSES
  MUST receive higher confidence than an otherwise-identical failing value.

#### Confidence scoring & thresholds

- **FR-015**: Confidence scoring MUST be deterministic — identical input under identical configuration
  MUST always yield identical entities and scores.
- **FR-016**: The scoring method MUST be explainable as a consistent rule set (a base score per type plus
  defined adjustments), not as per-value hand-picked numbers, so it can be described as a method in the
  thesis.
- **FR-017**: Confidence MUST increase when a value passes its checksum and when a recognised context
  label sits adjacent to it (e.g. "PESEL:", "NIP:", "nr rachunku"); it MUST decrease when the checksum
  fails or when no context label is present.
- **FR-018**: An identifier that appears with NO context label MUST still be detected, at reduced
  confidence (recall over precision).
- **FR-019**: Each entity type MUST have its own configurable minimum confidence threshold; any detection
  scoring below its type's threshold MUST be discarded from the returned list.
- **FR-020**: Thresholds MUST be held in a dedicated threshold configuration file (e.g. YAML/JSON),
  separate from the env-based startup settings (which remain cached for secrets/startup config); that
  file MUST be read live (per request or on file-change) so a threshold change takes effect on the next
  detection request WITHOUT restarting the system. Thresholds MUST NOT be stored in a way that
  re-introduces a Redis dependency on the detection path (cf. FR-031).
- **FR-021**: Default thresholds MUST be deliberately low so the engine favours recall over precision;
  false positives are acceptable and surfaced for human review.
- **FR-022**: A type threshold of 0 MUST surface every candidate the recognizer produces for that type
  ("paranoid" mode); a type threshold of 1 MUST effectively disable that type (no entities of that type
  returned).

#### Overlap resolution

- **FR-023**: When candidate spans overlap or one contains another, the engine MUST return the
  longer/containing span and MUST merge contained or near-duplicate detections so that a single best
  entity is returned per region.
- **FR-024**: A place/city name that falls within a detected postal address MUST be subsumed by the
  address span; no duplicate location entity is returned for it.
- **FR-025**: A street name that is a surname (e.g. "ul. Kowalskiego") MUST be treated as part of the
  address, not returned as a separate person entity.
- **FR-026**: A first name and last name MAY be returned either as a single person span or as two
  adjacent person spans; both outcomes are acceptable.

#### Operational surface

- **FR-027**: The system MUST expose a lightweight debug endpoint that accepts a piece of text and
  returns the detected entities (type, position, score, text, metadata), with no substitution and with
  no LLM involvement.
- **FR-028**: The system's existing health surface MUST reflect whether the underlying Polish language
  model is loaded and ready; when the model is unavailable the health surface MUST report a degraded
  overall state. This replaces the EPIC 1 placeholder model check and MUST reuse the existing health
  endpoint, its aggregation rule, its always-200 HTTP behaviour, and its response schema unchanged.
- **FR-030**: When the Polish language model is unavailable, the detection/debug endpoint MUST reject
  the request with HTTP 503 and MUST NOT return partial (regex/checksum-only) results. This extends the
  EPIC 1 dependency-gating behaviour to the model dependency for detection routes; the `/health`
  endpoint remains exempt from this gate and continues to report degraded (FR-028).
- **FR-031**: The detection/debug endpoint MUST be exempt from the EPIC 1 Redis-availability gate,
  because detection has no Redis dependency; it is gated only on model availability (FR-030). This
  exemption MUST be added alongside the existing `/health` exemption in the gate, without changing the
  gate's behaviour for any other route.

#### Quality

- **FR-029**: Each custom recognizer (PESEL, NIP, REGON, bank account, postal address) MUST ship with
  unit tests covering positive cases (valid values detected), negative cases (malformed values / bad
  checksums are not accepted as high-confidence), and edge cases (separators, post-2000 PESEL dates,
  REGON 9 vs 14, labelled vs unlabelled occurrences). Formal precision/recall/F1 evaluation against a
  gold standard is OUT OF SCOPE for this epic.

### Key Entities *(include if feature involves data)*

- **Detected PII entity**: The unit returned by the engine. Attributes: type; start offset and end
  offset (into the original text); confidence score (0–1); matched text (exact original substring); and
  optional type-specific metadata (e.g. PESEL gender and derived birth date, matched REGON variant).
- **Recognizer**: A per-type detector that scans the text and produces candidate spans, plus the
  validation signals (checksum pass/fail, presence of a context label) that feed scoring. Includes
  language-model-based recognizers (person, place) and custom Polish recognizers (PESEL, NIP, REGON,
  bank account, address, Polish dates/phones).
- **Confidence scoring method**: The deterministic, explainable rule set that turns a recognizer's
  validation signals (base score, checksum result, context-label presence) into a final 0–1 score.
- **Detection threshold configuration**: The set of per-type minimum confidence thresholds, held in a
  dedicated configuration file (YAML/JSON) separate from the env-based startup settings, read live at
  filter time so changes apply without a restart; supports the 0 ("paranoid") and 1 ("disabled")
  extremes.
- **Polish identifier validators**: The checksum/derivation logic for PESEL (control sum, gender, birth
  date with post-2000 offset), NIP (control sum), REGON (9- and 14-digit control sums), and bank account
  (mod-97).
- **Model-readiness status**: Whether the Polish language model is loaded and ready; consumed by the
  health surface as a tracked dependency (replacing the EPIC 1 stub).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can submit arbitrary Polish text to the debug surface and receive every detected
  entity with its type, character offsets, confidence score, exact matched text, and metadata — with no
  value substituted, stored, logged, or sent to any LLM.
- **SC-002**: For every returned entity, the substring extracted from the original input using the
  reported start/end offsets is identical to the reported matched text (including any separators).
- **SC-003**: Valid PESEL, NIP, REGON, and bank-account values that pass their checksums are detected and
  reported with the correct type and metadata (PESEL gender; REGON variant), and are scored higher than
  otherwise-identical values whose checksums fail.
- **SC-004**: Values that fail their checksum (bad PESEL/NIP/REGON/account) are still surfaced (not
  dropped), at lower confidence than passing values.
- **SC-005**: Running detection twice on identical input under identical configuration produces identical
  entities and identical scores (deterministic).
- **SC-006**: Setting a type's minimum threshold to 0 returns every candidate that type's recognizer
  produces; setting it to 1 returns no entities of that type.
- **SC-007**: Changing a threshold value is reflected on the next detection request with no restart of
  the system.
- **SC-008**: Overlapping or contained detections collapse to one entity per region — e.g. a 9-digit
  REGON inside a 14-digit REGON yields a single 14-digit entity, and a city inside a detected address
  yields no separate place entity.
- **SC-009**: A post-2000 PESEL and a NIP beginning with 0 are each detected and validated correctly
  (century/month offset handled; leading-zero NIP accepted).
- **SC-010**: Empty or whitespace-only input returns an empty entity list with no error.
- **SC-011**: Every custom recognizer has passing positive, negative, and edge-case unit tests covering
  the cases in FR-029.
- **SC-012**: When the Polish language model is loaded the health surface reports it available and
  contributes "ok"; when it is unavailable the health surface reports it unavailable and the overall
  status is "degraded", with the EPIC 1 HTTP/schema behaviour unchanged.

## Assumptions

- **Detection-only boundary**: Substitution/masking, reversible session mapping, persistence of
  detections, and LLM proxying are explicitly out of scope here and arrive in later epics; this layer
  only describes what it finds.
- **Entity-type vocabulary**: The free-text types (person, place/location, e-mail, phone, date) follow
  the recognizer framework's established type names, and the Polish structured types (PESEL, NIP, REGON,
  bank account, postal address) are custom types added by this epic. Exact identifier strings are an
  implementation/plan concern.
- **Person/place source**: Person and place detection is provided by the Polish language model (per the
  project constitution); these types have no checksum, so their confidence derives from the model's own
  score mapped into the scoring method, optionally adjusted by context.
- **Threshold live-reload mechanism**: Thresholds live in a dedicated file (YAML/JSON) separate from the
  env-based `Settings`; "without restarting" is satisfied by reading that file live at detection time
  (per-request read or file-change/mtime reload). The exact serialization format and read strategy are a
  plan-phase detail; storing thresholds in Redis is excluded, as it would re-introduce a Redis
  dependency on the detection path (cf. FR-031).
- **Debug surface intent**: The debug endpoint is for manual inspection in a trusted/development context,
  not a hardened public API; consistent with FR-007 it must not log submitted text. The endpoint is
  exempt from the EPIC 1 Redis-availability gate and is instead gated on model availability (FR-030,
  FR-031); authentication and other exposure controls are out of scope for this epic.
- **Polish phone formats**: National 9-digit numbers, optionally with a "+48"/"0048" country prefix and
  optional spaces/dashes, covering mobile and landline forms.
- **Worded Polish dates**: Use Polish month names in their inflected (genitive) forms (e.g. "stycznia"),
  optionally followed by the "r." year marker; partial/approximate dates beyond this are not required.
- **PESEL metadata scope**: At minimum gender is reported; the derived birth date is included where the
  encoded date is coherent. An incoherent embedded date lowers confidence but does not drop the
  detection.
- **mod-97 validation is optional**: Bank-account checksum validation via mod-97 is supported and feeds
  confidence, but a 26-digit value that does not pass (or is in a non-banking context) is still surfaced
  at low confidence rather than rejected.
- **Health surface reuse**: The health endpoint, aggregation rule, always-200 behaviour, and response
  schema from EPIC 1 are reused as-is; only the previously-stubbed model-readiness check becomes a real
  check.
- **Performance/throughput**: No specific latency or throughput target is defined for detection in this
  epic; large-document chunking and performance SLAs are out of scope.
- **No formal evaluation**: Precision/recall/F1 measurement against a labelled gold-standard corpus is
  out of scope; quality is demonstrated through unit tests and manual review via the debug surface.
