# Feature Specification: EPIC 3 — Realistic Fake-Data Generator and Reversible Session Mapping Store for Polish Civil-Law Contracts

**Feature Branch**: `im/03-fake-data-generator`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "EPIC 3 — Realistic fake-data generator and reversible session mapping store for Polish civil-law contracts. Build the layer that, given a detected PII entity, produces a realistic Polish synthetic replacement and remembers — within a session — which original maps to which fake, reversibly. It does three things: generate realistic substitutes (format-valid, checksum-passing identifiers; gender-consistent names; plausible dates), store the original↔fake mapping reversibly and securely (AES-256 at rest, expiring TTL, explicit clear, reviewable), and keep that mapping consistent across a multi-turn session including across Polish grammatical inflection (PERSON and LOCATION case handling). Two debug endpoints (replace forward, restore reverse) validate the round-trip in isolation; no LLM is called."

## Overview

This epic delivers the **substitution and reversible-mapping** layer of the anonymization gateway. It
sits between the detection layer (EPIC 2, already built) and the LLM proxying pipeline (a later epic).
Given Polish text and a session id, it (1) **generates** a realistic Polish synthetic replacement for
each detected PII entity, (2) **stores** the original↔fake mapping reversibly and securely so the
original can be recovered, and (3) keeps that mapping **consistent** across a multi-turn session,
including across Polish grammatical inflection.

The substitutes are realistic, never abstract placeholders: a person's name with a consistent gender, a
city, an address, an e-mail, a Polish phone number, a date, and the Polish national identifiers
(PESEL / NIP / REGON / bank account). The synthetic structured identifiers are **format-valid and pass
their own control sums** — a fake PESEL has a valid checksum and encodes the **same gender** as the real
one it replaces; a fake REGON keeps the original's 9- vs 14-digit variant; a fake date of birth lands in
a similar age range (±10 years). Realistic substitutes exist so a downstream LLM keeps the semantic
context (Constitution VII — Realistic Substitution).

The mapping is **reversible within the session**: given an original you can find its fake, and given a
fake you can recover the original. All stored personal data is **encrypted at rest with AES-256**; the
key never leaves the system and is never exposed to the provider or the client (Constitution III —
Reversibility within Session). Each session **expires after a configurable TTL** that any activity
refreshes, can be **explicitly cleared**, and can be **listed** for manual review.

Consistency is the core behavioural guarantee: the **same original always maps to the same fake** for
the lifetime of the session, references to the same entity worded differently resolve together (full
name "Jan Kowalski" and later "Kowalski" → the same fake person), genuinely different people who share a
surname root get **distinct** fakes, and the generator never reuses a fake already in play
(collision-free). Because Polish is inflected, all inflected forms of a PERSON or LOCATION
("Kowalski" / "Kowalskiego" / "Kowalskim"; "Kraków" / "w Krakowie") resolve to the same fake, and the
substitute is rendered in the **correct grammatical case** on the way out and the original restored in
the matching case on the way in. Inflection handling is pragmatic, not perfect (Constitution IX —
Simplicity over Completeness): common patterns are covered, rare/foreign/indeclinable names fall back to
the base form as a documented limitation.

Two **debug endpoints** validate the epic in isolation: a **replace** endpoint takes text + a session id,
reuses the EPIC 2 detection layer to find the PII, and returns the text with PII swapped for realistic
fakes plus the list of replacements and the session id; a companion **restore** endpoint takes text + a
session id and returns the text with the originals restored from the fakes (the reverse direction,
including inflection), so a reviewer can see the full round-trip working. Neither endpoint calls an LLM;
the full pipeline, logging/metrics, and an OpenAI-compatible surface are a later epic.

## Clarifications

### Session 2026-06-16

- Q: How should the store encrypt the two sides of a mapping, given that bidirectional lookup over randomized ciphertext is impossible? → A: Encrypt the **original PII only** (AES-256, randomized) — synthetic fakes are not real personal data, so they are stored as plaintext and serve as the direct fake→original reverse index; forward (original→fake) lookup uses a keyed-hash (e.g. HMAC) index of the normalized original. The encryption key is still never exposed (Constitution III/VIII unchanged).
- Q: When a later turn uses a surname alone and the session already holds two or more different full-name people sharing that surname, how does it resolve? → A: Treat the ambiguous surname-only mention as a **new, separate person** with its own fake — never guess which existing person. A single unambiguous match still reuses that person (FR-013). This is a documented limitation.
- Q: What is the default session TTL (sliding, refreshed on activity)? → A: **30 minutes** (configurable).
- Q: How are fake dates generated, given that reliably identifying a date of birth is hard? → A: Do **not** special-case date of birth — shift **every** fake date within ±10 years of the original. No DOB classification is required; any date stays plausible (Constitution IX).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Replace detected PII with realistic fakes and restore the original (round-trip) (Priority: P1)

A thesis reviewer (or a developer) submits a piece of Polish text and a session id to the **replace**
endpoint and gets back the same text with every detected PII value swapped for a realistic Polish
synthetic value — a believable name, city, address, e-mail, phone, date, PESEL, NIP, REGON, or bank
account — together with the list of replacements (original→fake, by type) and the session id. The
structured identifiers in the output are format-valid and pass their own checksums, a fake PESEL carries
the same gender as the original, and a fake date of birth stays in a similar age range. The reviewer then
submits the substituted text and the same session id to the **restore** endpoint and gets the original
PII back, proving the mapping is reversible. No LLM is involved.

**Why this priority**: This is the headline deliverable and the only way the layer is exercised and
evaluated in this epic — a self-contained "give me text + a session, get realistic fakes back, then get
the originals back" round-trip that proves generation and the reversible store work end to end and can be
demonstrated without the LLM pipeline.

**Independent Test**: Submit a Polish snippet (with a name, a city, an e-mail, a phone, a date, and at
least one structured identifier such as a PESEL) plus a fresh session id to the replace endpoint; confirm
each detected value is replaced by a realistic, type-correct, checksum-valid fake and a replacement list
+ session id are returned; then submit the returned text and the same session id to the restore endpoint
and confirm the original text is reconstructed. Confirm empty input returns an empty result and an empty
session without error.

**Acceptance Scenarios**:

1. **Given** Polish text containing a person's name, a city, an e-mail, a Polish phone number and a date,
   and a fresh session id, **When** the text is submitted to the replace endpoint, **Then** each detected
   value is replaced by a realistic Polish synthetic value of the same type (no abstract placeholder such
   as "[PERSON_1]"), and the response includes the substituted text, the list of replacements, and the
   session id.
2. **Given** a detected PESEL, NIP, REGON and bank account, **When** they are replaced, **Then** every
   fake identifier is format-valid and passes its own control sum, the fake PESEL encodes the same gender
   as the original, the fake REGON keeps the original's 9- vs 14-digit variant, and the fake phone has a
   valid Polish format.
3. **Given** a detected date of birth, **When** it is replaced, **Then** the fake date is plausible and
   falls within ±10 years of the original so the surrounding text stays believable.
4. **Given** text that was run through the replace endpoint in a session, **When** the substituted text
   and the same session id are submitted to the restore endpoint, **Then** the original PII values are
   restored in place of the fakes and the reconstructed text matches the original.
5. **Given** an empty (or whitespace-only) input and a session id, **When** it is submitted to either
   endpoint, **Then** an empty result and an (empty) session are returned with no error and no LLM call.
6. **Given** any request to either endpoint, **When** it is processed, **Then** no original personal data
   is written to logs in readable form and no LLM is contacted (Constitution VIII).

---

### User Story 2 - Keep substitutions consistent across a multi-turn session (Priority: P2)

Across several turns of the same session, the reviewer expects the layer to be consistent: the same
original value always yields the same fake (asking again never produces a fresh one), the same entity
referred to differently resolves to one fake (a person introduced as "Jan Kowalski" and later mentioned
as just "Kowalski" maps to the same fake person), two genuinely different people who merely share a
surname root ("Anna Kowalska" and "Jan Kowalski") get separate fakes, the same value written with or
without separators is one mapping, and the same literal value under two different entity types is two
independent mappings. No fake collides with a fake already used elsewhere in the session.

**Why this priority**: Cross-turn consistency is what makes the layer usable by the later LLM pipeline and
is a core thesis claim, but it refines and depends on the generation + store from US1.

**Independent Test**: In one session, submit the same original twice across two turns and confirm the same
fake is returned both times; introduce a full name then reference the surname alone and confirm the same
fake person; submit two different people who share a surname root and confirm distinct fakes; submit a
PESEL once with dashes and once without and confirm a single fake; submit the same literal string as two
different entity types and confirm two independent fakes.

**Acceptance Scenarios**:

1. **Given** an original value already mapped in a session, **When** the same value is submitted again in
   the same or a later turn, **Then** the previously assigned fake is returned — never a freshly generated
   one (idempotent within the session).
2. **Given** a person introduced by full name ("Jan Kowalski") in an earlier turn, **When** a later turn
   refers to them by surname only ("Kowalski"), **Then** the same fake person is reused.
3. **Given** two genuinely different people who share a surname root ("Anna Kowalska" and "Jan
   Kowalski"), **When** both are processed, **Then** each receives a separate fake — matching is on the
   whole name within the same entity type, not on shared word fragments.
4. **Given** the same identifier written with separators and without (NIP "123-456-32-18" vs
   "1234563218"), **When** both forms appear in the session, **Then** they are treated as the same value
   and map to a single fake.
5. **Given** the same literal value detected under two different entity types, **When** both are
   processed, **Then** they are stored as two independent mappings, each with its own fake.
6. **Given** the generator's first candidate fake already exists elsewhere in the session, **When** it
   generates, **Then** it retries and ultimately returns a value that is not already in use anywhere in
   the session (collision-free).

---

### User Story 3 - Handle Polish grammatical inflection in both directions (Priority: P2)

Because Polish is inflected, the reviewer expects a surname or city to be recognised and rendered in
whatever grammatical case it appears in. A surname appearing as "Kowalski", "Kowalskiego",
"Kowalskiemu" or "Kowalskim" all resolves to the same fake person, and the fake is inserted in the
matching case so the outgoing text stays grammatical; on restore, the original is put back in the
matching case so the incoming text stays grammatical too. First name and surname inflect independently
("Jana Kowalskiego"), cities inflect ("Kraków" / "w Krakowie"), and addresses are treated as one atomic
block (replaced and restored whole, not internally inflected). The approach is pragmatic: common patterns
are covered and rare/foreign/indeclinable names fall back to the base form as a documented limitation.

**Why this priority**: Case-aware substitution is the distinctive, linguistically hard contribution of
this epic and is what the thesis evaluates most closely, but it builds on the consistent store from
US1/US2 and is explicitly allowed to be partial.

**Independent Test**: Submit the same person across several cases (nominative, genitive, dative,
instrumental) and confirm all map to one fake rendered in the correct case each time; submit "Jana
Kowalskiego" and confirm first name and surname are each inflected; submit a city in an oblique case
("w Krakowie") and confirm it is recognised and the fake city is rendered in the matching case; submit a
rare/foreign surname and confirm it is still mapped consistently but shown in base form; round-trip each
through the restore endpoint and confirm the original is restored in the matching case.

**Acceptance Scenarios**:

1. **Given** a surname appearing in several grammatical cases across a session ("Kowalski",
   "Kowalskiego", "Kowalskim"), **When** they are processed, **Then** all forms resolve to the same fake
   person and the fake is inserted in the correct grammatical case for each occurrence.
2. **Given** a fake surname inserted in an oblique case in outgoing text, **When** the text is restored,
   **Then** the original surname is put back in the matching grammatical case so the restored text stays
   grammatical.
3. **Given** an inflected full name "Jana Kowalskiego" (genitive of "Jan" + genitive of "Kowalski"),
   **When** it is processed, **Then** the first name and surname are inflected independently and both
   resolve to the same fake person.
4. **Given** a city in an oblique case ("w Krakowie"), **When** it is processed, **Then** it resolves to
   the same fake city as its nominative form and the fake is rendered in the matching case.
5. **Given** an inflected form the detector has lemmatised to its base ("Kowalskiego" → "Kowalski"),
   **When** it is processed, **Then** it maps to the same fake as the nominative form and is rendered back
   in the matching case.
6. **Given** a rare/foreign or indeclinable surname with no known inflection pattern, **When** it is
   processed, **Then** it is still mapped consistently to one fake but is shown in its base form (a
   documented limitation).
7. **Given** a detected postal address and a standalone city elsewhere in the same text, **When** they
   are processed, **Then** the address is replaced and restored as one atomic block (not internally
   inflected) while the standalone city is inflected.

---

### User Story 4 - Securely store, expire, clear, and review session mappings (Priority: P3)

An operator and a reviewer need the mapping store to be secure and operable. All stored personal data is
encrypted at rest with AES-256 and is unreadable without the key, which never leaves the system and is
never exposed to the provider or the client. Each session expires after a configurable time-to-live, and
any activity in the session refreshes the expiry; a session can be explicitly cleared, which removes all
of its mappings at once. A reviewer can list all mappings currently held for a session for manual
inspection. Logs and stored keys never contain original personal data in readable form. If the store is
restarted mid-session the session is lost, and starting a new session is the accepted recovery.

**Why this priority**: Secure, expiring, reviewable storage is required for a trustworthy and
demonstrable system (and is mandated by the constitution), but it is operability/governance layered on
top of the functional round-trip in US1.

**Independent Test**: Inspect the raw stored representation and confirm personal values are encrypted
(unreadable without the key); let a session's TTL elapse and confirm its mappings are gone; perform
activity before the TTL and confirm the expiry is refreshed; explicitly clear a session and confirm all
its mappings are removed at once; list a session's mappings and confirm the reviewer sees the
original↔fake pairs; inspect logs and stored keys and confirm no original personal data appears in
readable form; restart the store mid-session and confirm the session is lost and a new session starts
fresh.

**Acceptance Scenarios**:

1. **Given** mappings stored in a session, **When** the raw stored representation is inspected without the
   key, **Then** the personal values are encrypted (AES-256) and unreadable, and the key is never present
   in stored data, logs, or anything sent to the provider or client.
2. **Given** a session with a configured TTL, **When** the TTL elapses with no activity, **Then** the
   session and all its mappings are gone; **and When** any activity occurs before expiry, **Then** the
   expiry is refreshed.
3. **Given** an active session, **When** it is explicitly cleared, **Then** all of its mappings are
   removed at once and subsequent lookups in that session find nothing.
4. **Given** an active session with several mappings, **When** a reviewer requests the session's mappings,
   **Then** all currently-held original↔fake pairs for that session are returned for inspection.
5. **Given** any processing in a session, **When** logs and stored keys are examined, **Then** they
   contain no original personal data in readable form — only encrypted values and non-identifying
   metadata such as entity types, counts, and timings (Constitution VIII).
6. **Given** an active session, **When** the underlying store is restarted, **Then** the session is lost;
   starting a new session is the expected and accepted recovery (no requirement to survive a restart).

---

### Edge Cases

- **Surname-only later reference**: a later turn refers to a person by surname only after an earlier turn
  introduced the full name → the same fake is reused (coreference within the session).
- **Shared surname root, different people**: "Anna Kowalska" vs "Jan Kowalski" → distinct fakes; matching
  is on the whole name within the same entity type, not on shared word fragments.
- **Ambiguous surname-only reference**: a later turn says just "Kowalski" while the session already holds
  two different people who share that surname ("Jan Kowalski" and "Adam Kowalski") → treated as a new,
  separate person (the system never guesses); only an unambiguous single match is reused.
- **Post-2000 PESEL for a woman**: the fake PESEL still encodes the correct gender and passes the checksum
  even though the original's month digits carry the post-2000 offset.
- **Generator collision**: the first candidate fake is already in use in the session → retry until a
  unique value is produced; uniqueness within the session is guaranteed.
- **Lemmatised inflected surname**: "Kowalskiego" lemmatised to base "Kowalski" maps to the same fake as
  the nominative and is rendered back in the matching case.
- **Rare/foreign/indeclinable surname**: still mapped consistently to one fake, but shown in base form (a
  documented limitation, Constitution IX).
- **Independent first-name/surname inflection**: "Jana Kowalskiego" = genitive of "Jan" + genitive of
  "Kowalski"; each part is inflected separately and both resolve to the same fake person.
- **Address vs standalone city**: an address is replaced and restored as one atomic block; a standalone
  city elsewhere is inflected.
- **Separators vs none**: a NIP as "1234563218" and as "123-456-32-18" is the same value → one fake.
  (A PESEL, by contrast, is always an unbroken 11-digit string — it has no separator form.)
- **Same literal, two types**: the same literal value detected under two different entity types → two
  independent mappings, each with its own fake.
- **Session expiry / explicit clear**: when the TTL elapses or the session is cleared, its mappings are
  gone and a new session starts fresh.
- **Empty input**: empty (or whitespace-only) text returns an empty result and an (empty) session without
  error.
- **Store restart mid-session**: the session is lost; starting a new session is the accepted recovery.

## Requirements *(mandatory)*

### Functional Requirements

#### Realistic substitution / generation

- **FR-001**: For each detected entity type (person name, city/location, postal address, e-mail, phone,
  date, PESEL, NIP, REGON, bank account), the system MUST generate a realistic Polish synthetic
  replacement that looks like genuine data of the same type. Abstract placeholder tokens (e.g.
  "[PERSON_1]") are FORBIDDEN (Constitution VII — Realistic Substitution).
- **FR-002**: A fake person name MUST have a consistent gender — first name and surname form a coherent,
  same-gender Polish name.
- **FR-003**: A fake PESEL MUST pass the PESEL control sum AND encode the SAME gender as the original it
  replaces; when the original encodes a post-2000 birth date (month offset), the generated fake remains
  checksum-valid and gender-correct.
- **FR-004**: A fake NIP MUST pass the NIP control sum; a fake REGON MUST pass the REGON control sum AND
  keep the original's 9- vs 14-digit variant; a fake bank account number MUST be a valid Polish account
  format and pass its checksum.
- **FR-005**: A fake Polish phone number MUST have a valid Polish format; a fake e-mail and a fake postal
  address MUST be realistic Polish-looking values of their type.
- **FR-006**: A fake date MUST stay plausible: EVERY fake date MUST fall within ±10 years of the original
  so the surrounding text stays believable (e.g. a date of birth keeps a similar age range). Dates are
  NOT classified as birth vs non-birth — the same ±10-year window applies to all of them, so no
  date-of-birth detection is required (Constitution IX — Simplicity over Completeness).

#### Reversible, secure session mapping store

- **FR-007**: Within a session the mapping MUST be bidirectional — given an original, the system returns
  its fake; given a fake, the system recovers the original.
- **FR-008**: All stored ORIGINAL personal data MUST be encrypted at rest with AES-256 (randomized) and
  MUST be unreadable without the key. Synthetic fake values are NOT real personal data and MAY be stored
  in plaintext, serving as the direct fake→original reverse index; the forward (original→fake) direction
  MUST be resolvable without decrypting every record (e.g. via a keyed-hash index of the normalized
  original). The key MUST never leave the system and MUST never be exposed to the LLM provider or the
  client (Constitution III — Reversibility within Session).
- **FR-009**: Each session MUST expire after a configurable time-to-live (TTL), defaulting to 30 minutes;
  any activity in the session MUST refresh the expiry (sliding expiry).
- **FR-010**: A session MUST be explicitly clearable; clearing removes all of its mappings at once.
- **FR-011**: A reviewer MUST be able to list all mappings currently held for a session (for manual
  inspection/debugging).

#### Consistency within a session

- **FR-012**: The same original value MUST always map to the same fake for the lifetime of the session —
  asking again, in the same or a later turn, MUST return the same fake, never a freshly generated one.
- **FR-013**: Consistency MUST hold across references to the same entity worded differently: a person
  introduced by full name and later referenced by surname only MUST resolve to the same fake person when
  exactly ONE stored person matches. Matching MUST be on the whole name within the same entity type, not
  on shared word fragments. When a surname-only mention is AMBIGUOUS — two or more stored people share
  that surname — it MUST be treated as a NEW, separate person with its own fake (the system never guesses
  which existing person is meant); this is a documented limitation.
- **FR-014**: Two genuinely different entities that merely share a word root (e.g. "Anna Kowalska" vs
  "Jan Kowalski") MUST receive separate mappings.
- **FR-015**: The generator MUST never return a fake value already in use elsewhere in the same session;
  on collision it MUST retry and ultimately guarantee a value unique within the session (collision-free).

#### Polish inflection (case handling)

- **FR-016**: For PERSON and LOCATION entities, all inflected forms of the same entity MUST resolve to the
  same fake (e.g. "Kowalski"/"Kowalskiego"/"Kowalskim"; "Kraków"/"w Krakowie").
- **FR-017**: When inserting a fake into outgoing text, the substitute MUST be rendered in the grammatical
  case of the original occurrence; when restoring the original into incoming text, the original MUST be
  rendered in the grammatical case of the fake occurrence — so the text stays grammatical in both
  directions.
- **FR-018**: A first name and a surname MUST be allowed to inflect independently (e.g. "Jana
  Kowalskiego" = genitive of "Jan" + genitive of "Kowalski").
- **FR-019**: Postal addresses MUST be handled atomically — replaced as one whole block and matched as one
  whole block, with their internal parts NOT separately inflected — while a standalone city is inflected.
- **FR-020**: Inflection coverage MUST be pragmatic: the common Polish patterns are covered (adjectival
  surnames in -ski/-ska, consonant-ending masculine names, -a-ending feminine names, common city
  patterns). Rare or foreign / indeclinable names MUST fall back to the base form. This partial coverage
  is an explicitly documented limitation (Constitution IX — Simplicity over Completeness).

#### Operational surface (debug only, no LLM)

- **FR-021**: The system MUST expose a debug **replace** endpoint that accepts Polish text and a session
  id, reuses the EPIC 2 detection layer to find the PII, and returns the text with PII replaced by
  realistic fakes, the list of replacements, and the session id. It MUST NOT call any LLM.
- **FR-022**: The system MUST expose a companion debug **restore** endpoint that accepts text and a
  session id and returns the text with the original PII restored from the fakes (the reverse direction,
  including correct inflection). It MUST NOT call any LLM.
- **FR-023**: Empty (or whitespace-only) input MUST return an empty result and an (empty) session without
  error, on both endpoints.

#### Cross-cutting rules

- **FR-024**: The same original written with or without separators (e.g. a NIP as "1234563218" vs
  "123-456-32-18") MUST be treated as the same value and map to a single fake (matching on a normalized
  form). Note: this applies to types that genuinely have a separator form (NIP, bank account/NRB); a
  PESEL is always an unbroken 11-digit string and has no dashed/spaced variant.
- **FR-025**: The same literal value detected under two different entity types MUST be treated as two
  independent mappings, each with its own fake.
- **FR-026**: Logs and stored keys MUST never contain original personal data in readable form — only
  encrypted values and non-identifying metadata such as entity types, counts, and timings (Constitution
  VIII — No PII in Logs).

#### Robustness & quality

- **FR-027**: If the underlying mapping store is restarted mid-session, the session and its mappings MAY
  be lost; starting a new session is the accepted recovery. The system MUST NOT be required to survive a
  store restart, and MUST behave correctly (empty session) for a session id whose data is gone.
- **FR-028**: The generators, the consistency/collision logic, the inflection handling (including the
  base-form fallback), and the full replace→restore round-trip MUST each be covered by unit tests for the
  positive, negative, and edge cases enumerated above (e.g. checksum validity, gender preservation, REGON
  variant preservation, ±10-year DOB range, coreference, distinct-people-shared-root, separator
  normalization, case-correct round-trip). Formal precision/recall evaluation is OUT OF SCOPE.

### Key Entities *(include if feature involves data)*

- **Session**: The unit of reversible mapping scope. Attributes: a session id; a TTL/expiry that any
  activity refreshes; a collection of mappings. Can be explicitly cleared (all mappings removed at once)
  and listed for review. Holds no readable personal data — all personal values are encrypted at rest.
- **Mapping**: A single original↔fake correspondence within a session, keyed by entity type and a
  normalized original value, supporting lookup in both directions. The original value is stored AES-256
  encrypted (randomized) and is unreadable without the key; the synthetic fake is stored in plaintext
  (not real PII) and serves as the direct fake→original reverse index, while a keyed-hash index of the
  normalized original powers the forward direction.
- **Synthetic value generator**: The per-type producer of realistic Polish fakes — names (gender-correct),
  cities, addresses, e-mails, phones (valid Polish format), dates (plausible; DOB within ±10 years), and
  the national identifiers PESEL (checksum + same gender), NIP (checksum), REGON (checksum + same 9-/14-
  digit variant), and bank account (checksum). Guarantees session-uniqueness via retry on collision.
- **Inflection handler**: The pragmatic case-aware component that recognises inflected forms of PERSON and
  LOCATION, resolves them to a single fake, renders the fake in the correct grammatical case on output and
  the original in the matching case on restore, inflects first name and surname independently, treats
  addresses atomically, and falls back to base form for unknown/foreign/indeclinable patterns.
- **Replacement**: An item in the replace endpoint's response — the original value, its fake, the entity
  type, and its position/occurrence — describing one substitution performed in the submitted text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can submit Polish text + a session id to the replace endpoint and receive the
  text with every detected PII value replaced by a realistic, type-correct Polish synthetic value (no
  abstract placeholders), plus the replacement list and session id — with no LLM call.
- **SC-002**: Every fake structured identifier returned is format-valid and passes its own control sum: a
  fake PESEL passes the checksum and encodes the same gender as the original; a fake NIP and bank account
  pass their checksums; a fake REGON passes its checksum and keeps the original's 9- vs 14-digit variant;
  a fake phone has a valid Polish format.
- **SC-003**: Every fake date lands within ±10 years of the original (no birth-vs-non-birth
  classification), keeping the surrounding text plausible.
- **SC-004**: Submitting the substituted text + the same session id to the restore endpoint reconstructs
  the original text, demonstrating a reversible round-trip — including for inflected occurrences.
- **SC-005**: Asking for the same original twice in a session returns the identical fake both times (never
  a freshly generated one), and a full name followed by a surname-only reference resolves to the same fake
  person.
- **SC-006**: Two genuinely different people who share a surname root receive distinct fakes; the same
  value written with and without separators yields a single fake; the same literal under two entity types
  yields two independent fakes.
- **SC-007**: No fake value is ever reused for a different original within the same session (collision-free,
  guaranteed by retry).
- **SC-008**: All inflected forms of the same PERSON or LOCATION resolve to one fake, and the fake is shown
  in the correct grammatical case on output while the original is restored in the matching case — for the
  covered patterns; rare/foreign/indeclinable names are still mapped consistently and shown in base form.
- **SC-009**: Stored personal data is encrypted (AES-256) and unreadable without the key; the key never
  appears in stored data, logs, or anything sent to the provider or client; logs and stored keys contain
  no original personal data in readable form.
- **SC-010**: A session expires after its configured TTL, the expiry is refreshed by activity, an explicit
  clear removes all mappings at once, and a reviewer can list all mappings currently held for a session.
- **SC-011**: Empty or whitespace-only input returns an empty result and an empty session without error;
  after a store restart, a previously-active session id behaves as an empty session and a new session
  starts fresh.
- **SC-012**: The generators, consistency/collision logic, inflection handling (with base-form fallback),
  and the replace→restore round-trip are each covered by passing positive, negative, and edge-case unit
  tests.

## Assumptions

- **Layer boundary**: This epic covers substitution generation + the reversible session store + the two
  debug endpoints. PII **detection** is reused from EPIC 2 (the replace endpoint calls it); LLM proxying,
  an OpenAI-compatible surface, and production logging/metrics are explicitly later epics and out of scope
  here. No LLM is called by either endpoint.
- **Session id handling**: The endpoints accept a session id from the caller. A reasonable default is that
  an absent/blank session id starts a fresh session and the chosen/generated id is returned in the
  response; the exact id format and generation strategy are a plan-phase detail.
- **TTL default & refresh**: The TTL is configurable (consistent with EPIC 1 settings) and defaults to
  **30 minutes** (clarified 2026-06-16); "any activity refreshes the expiry" means a sliding expiry reset
  on each replace/restore/list touch of the session. The refresh granularity is a plan-phase detail.
- **Encryption & key handling**: AES-256 (per the constitution) with a single system-held symmetric key
  sourced from secure configuration (consistent with EPIC 1's settings handling); key rotation and
  multi-tenant key management are out of scope for the prototype. Encryption scope is fixed (clarified
  2026-06-16): only original PII values are encrypted (randomized AES-256); synthetic fakes are stored in
  plaintext as the reverse index and forward lookups use a keyed-hash index of the normalized original.
  The exact index/serialization mechanics (e.g. HMAC choice) remain a plan-phase detail.
- **Store technology**: The session store is the EPIC 1 Redis instance with TTL/expiry; durability across
  a Redis restart is explicitly NOT required (FR-027). Because these endpoints depend on the store, they
  are subject to the EPIC 1 Redis-availability gate (unlike the EPIC 2 detection-only endpoints); the
  replace endpoint additionally depends on the detection model. Exact gating wiring is a plan-phase
  detail.
- **Coreference matching**: "Same entity worded differently" is resolved pragmatically — a surname
  contained in (or equal to) a previously seen full name within the same entity type resolves to the same
  person when exactly one stored person matches, while distinct full names that merely share a root do
  not. When a surname-only mention matches two or more stored people it is treated as a new, separate
  person (clarified 2026-06-16) — the system never guesses. Matching operates only within one entity
  type; the precise normalized-matching mechanics are a plan-phase detail.
- **Inflection scope**: Case handling applies to PERSON and LOCATION only; addresses are atomic; other
  types (e-mail, phone, identifiers, dates) are not inflected. Coverage is the common-pattern set listed
  in FR-020 with a base-form fallback; full morphological correctness across all Polish cases is
  explicitly not a goal (documented limitation per Constitution IX).
- **Restore direction**: The restore endpoint locates the session's fake values (including their inflected
  forms) in the supplied text and swaps the originals back; it is driven by the session store rather than
  by re-running NER detection. The exact location strategy is a plan-phase detail.
- **Realistic-substitution toolchain**: Synthetic Polish values are produced with the project's fake-data
  tooling (Faker `pl_PL` per the constitution) augmented by custom checksum-valid generators for the
  Polish identifiers; exact library wiring is a plan-phase detail.
- **No performance target**: No specific latency or throughput target is defined for this epic; large-
  document handling and performance SLAs are out of scope.
- **Trusted debug context**: The two endpoints are for manual inspection in a trusted/development context,
  not a hardened public API; authentication and other exposure controls are out of scope for this epic,
  but the no-PII-in-logs rule (FR-026) still holds.
