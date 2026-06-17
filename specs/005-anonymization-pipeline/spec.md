# Feature Specification: EPIC 4 — Anonymization Pipeline and the First End-to-End LLM Round-Trip

**Feature Branch**: `im/04-pseudonimization-pipeline`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "EPIC 4 — Anonymization pipeline and the first end-to-end LLM round-trip (vertical slice). Build the orchestrator that ties the existing detection layer (EPIC 2) and the existing substitution + reversible mapping store (EPIC 3) into one flow, and — for the first time — closes a full round-trip through a REAL LLM: pseudonymize the user's request, send it to the LLM, then de-pseudonymize the LLM's answer. The headline deliverable is a working chat endpoint that proves the whole gateway works from end to end without ever exposing original personal data to the LLM."

## Overview

This epic delivers the **orchestration and first live LLM round-trip** of the anonymization gateway. EPIC 2
detects PII and EPIC 3 produces realistic Polish fakes, stores the original↔fake mapping reversibly and
securely, and keeps it consistent across a multi-turn session — but only through two **debug** endpoints
with **no LLM**, and with the substitution logic living inline inside those handlers. This epic extracts
that orchestration into a **reusable pipeline component**, adds the **fuzzy fallback** the real restore
path is still missing, connects **one real LLM**, and exposes a minimal **chat endpoint** so the system
can finally be demonstrated answering questions about a Polish civil-law contract while the provider only
ever sees synthetic data.

The pipeline has two stages. The **inbound (pseudonymize)** stage detects PII, substitutes
session-consistent realistic fakes, and persists the mapping — reusing the EPIC 2 detection and the EPIC 3
generator + store rather than reimplementing them. The **outbound (de-pseudonymize)** stage restores the
originals in the LLM's answer. The pipeline is a **programmatically callable internal component**, not just
an HTTP handler, because the chat endpoint and later epics consume it directly.

In chat mode the **whole conversation** (the messages array) is sent to the LLM each turn. Assistant
messages from earlier turns have already been de-pseudonymized for display and therefore contain original
PII, so the inbound stage **pseudonymizes every message in the array each turn**, not only the last one —
no original ever reaches the LLM. The client↔gateway hop is inside the trust boundary; only the
gateway↔LLM hop is protected. Re-pseudonymizing the same content is **deterministic** (same original →
same fake) thanks to session consistency from EPIC 3.

The outbound stage gains a **bounded fuzzy fallback** under strict safety rules. The exact + inflection
restore from EPIC 3 runs first; when a real LLM renders a fake in an inflected form the form table did not
foresee, the fuzzy pass recovers it. It applies **only to PERSON and LOCATION** entities — structured
identifiers (PESEL, NIP, REGON, bank account), e-mail and phone are **exact-only** (a one-character edit on
a PESEL is a different, valid-looking number). It runs only on tokens the exact pass did not replace, never
touches an already-restored span, is token-level and word-boundary with a minimum token length of 4,
requires a shared **prefix anchor** (roughly ≥ 60% of the shorter token) before a match is accepted because
Polish inflection changes the suffix not the stem, and uses a length-aware bounded **edit distance (≤ 2)**
as the final gate. The best match is deterministic; on an unresolvable tie it skips (never guesses). On a
fuzzy hit the original is restored in its **base (nominative) form** — a documented limitation: identity is
restored correctly even if the surrounding grammar is slightly off. An invented name absent from the input
is left untouched because the prefix anchor prevents accidental restoration.

One real LLM sits behind an **abstract provider port**: a minimal interface (send messages → assistant
text; a reachability check) with one concrete implementation talking to a **local Ollama** server over REST,
plus a deterministic, **network-free echo/stub provider** so pipeline round-trip tests stay fast and
reproducible. The provider port keeps the pipeline decoupled from any specific provider (Constitution IV).

The user-facing surface is a single minimal **`POST /v1/chat/completions`** endpoint (happy path),
OpenAI-compatible in shape: it accepts a messages array and an optional session id, runs
inbound → LLM → outbound, and returns the assistant's answer plus the session id. The full response
contract (anonymization metadata, finish_reason passthrough, exhaustive validation), request
logging/metrics middleware, the OpenAI/Anthropic adapters and model-based router, the session GET/DELETE
endpoints, and streaming/SSE are all explicitly **later epics**. The standalone no-LLM `POST /v1/anonymize`
is **not** built — EPIC 3's `POST /v1/pseudonymize` already serves that purpose, so it is dropped as
redundant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-end pseudonymized chat round-trip (Priority: P1)

A thesis reviewer (or a developer) sends a single-turn Polish chat request — text containing a person, a
city and at least one structured identifier — to the chat endpoint with a session id. The gateway
pseudonymizes the request so the outgoing call to the LLM contains **only synthetic values**, sends it to
the LLM, restores the originals in the LLM's answer, and returns the assistant's answer plus the session id.
The reviewer sees a coherent answer about the contract with the real names/identifiers in place, while the
provider only ever saw fakes.

**Why this priority**: This is the headline deliverable — the first proof that the whole gateway works end
to end without exposing original personal data to the LLM. It exercises the pipeline orchestrator and the
chat endpoint together and is the single most demonstrable outcome of the epic. With the deterministic
stub provider it is fully and reproducibly testable on its own.

**Independent Test**: Send a one-message conversation (a Polish snippet with a name, a city and a PESEL) and
a fresh session id to the chat endpoint, backed by the stub provider; capture the messages actually handed
to the provider and confirm they contain only synthetic values (no original PII); confirm the returned
answer has the originals restored in place and the response carries the session id.

**Acceptance Scenarios**:

1. **Given** a single user message of Polish text containing a person, a city and at least one structured
   identifier and a fresh session id, **When** it is sent to the chat endpoint, **Then** the messages handed
   to the LLM contain only synthetic values and no original PII.
2. **Given** the same request, **When** the LLM returns an answer that references the fake values, **Then**
   the response returned to the caller has the originals restored in place and includes the session id.
3. **Given** no session id is supplied, **When** the request is processed, **Then** a new session is started
   and its id is returned so the caller can continue the conversation.
4. **Given** any chat request, **When** it is processed, **Then** no original personal data appears in logs
   or in any outgoing request to the LLM (Constitution VIII, I).

---

### User Story 2 - Multi-turn history re-pseudonymized consistently every turn (Priority: P2)

Across several turns of the same session the whole conversation is resent to the LLM each turn. Earlier
assistant messages were de-pseudonymized for display and now contain original PII, so on every turn the
gateway re-pseudonymizes **every message in the array** — user and assistant alike — before the LLM is
called, and does so **consistently**: the same original always becomes the same fake it was assigned earlier
in the session. No original from any earlier turn leaks to the provider.

**Why this priority**: Multi-turn chat is the real usage mode and the place the most subtle leak could
happen (an original re-entering through a prior assistant message). It depends on the round-trip from US1
but is essential for a usable chat gateway.

**Independent Test**: Run a two-turn conversation in one session where the second request resends an earlier
(already de-pseudonymized) assistant message containing PII; capture what is handed to the provider on the
second turn and confirm every original across the whole history is replaced, and that each original maps to
the same fake it received on the first turn (deterministic re-pseudonymization).

**Acceptance Scenarios**:

1. **Given** a multi-turn conversation whose history includes an earlier assistant message containing
   original PII, **When** a later turn is sent, **Then** every message in the array is pseudonymized before
   the LLM call, not only the last one.
2. **Given** an original that was already mapped to a fake earlier in the session, **When** it reappears in
   any message of a later turn, **Then** it is replaced by the **same** fake (deterministic, session-consistent).
3. **Given** the client↔gateway hop is trusted while only the gateway↔LLM hop is protected, **When** the
   assistant's answer is returned, **Then** it is de-pseudonymized (originals in place) for display, even
   though it will be re-pseudonymized on the next turn.

---

### User Story 3 - Fuzzy fallback restores inflected fakes safely (Priority: P2)

A real LLM sometimes renders a fake PERSON or LOCATION in a grammatical case the form table did not foresee.
The reviewer expects the original to still be restored: after the exact + inflection pass, a bounded fuzzy
fallback recovers such tokens and restores the original in its base (nominative) form. The fallback is
deliberately conservative — it never fires on identifiers, e-mail or phone, never re-touches an
already-restored span, and never restores a name the input never contained.

**Why this priority**: Connecting a real LLM (rather than the deterministic debug round-trip) is exactly
what surfaces unforeseen inflections, so the fuzzy fallback is what makes the real restore path trustworthy.
It builds on the outbound stage from US1.

**Independent Test**: Feed the outbound stage an answer that inflects a fake surname/city in a form not in
the table and confirm the original is restored in base form; feed an answer that inflects a fake
identifier-like string and confirm fuzzy does **not** fire (the identifier is left as-is); feed an answer
containing a brand-new name absent from the input and confirm it is left untouched.

**Acceptance Scenarios**:

1. **Given** an LLM answer that inflects a fake PERSON or LOCATION in a form the exact + inflection pass did
   not replace, **When** the outbound stage runs, **Then** the fuzzy fallback restores the original in its
   base (nominative) form.
2. **Given** an LLM answer that inflects (or lightly perturbs) a fake PESEL/NIP/REGON/bank account, e-mail or
   phone, **When** the outbound stage runs, **Then** the fuzzy fallback does **not** fire — these types are
   exact-only.
3. **Given** a token the exact pass already restored, **When** the fuzzy pass runs, **Then** it never
   re-touches that span.
4. **Given** a candidate token shorter than 4 characters, or one that does not share the required common
   prefix with any stored fake, or whose bounded edit distance to every stored fake exceeds the gate, **When**
   the fuzzy pass runs, **Then** it is not matched.
5. **Given** an LLM answer that invents a name absent from the input, **When** the outbound stage runs,
   **Then** it is left untouched (the prefix anchor prevents accidental restoration) — an accepted limitation.
6. **Given** two stored fakes that match a candidate token equally well (an unresolvable tie), **When** the
   fuzzy pass runs, **Then** it skips the token rather than guessing.

---

### User Story 4 - Talk to a real local LLM through a provider port and fail gracefully (Priority: P2)

The gateway talks to a real LLM through an abstract provider port so no component is coupled to a specific
provider (Constitution IV). For this epic the concrete provider is a local Ollama server reached over REST,
with a deterministic network-free echo/stub provider available for tests. When the LLM cannot be reached,
times out, or is missing its model, the chat endpoint fails with a readable message and a sensible status
code, and the session id is preserved so the caller can retry. Malformed requests are rejected before any
LLM call.

**Why this priority**: "The first end-to-end round-trip through a REAL LLM" is the epic's framing, and a
demo that hangs or 500s when Ollama is down is not demonstrable. The provider port and graceful failure are
required for a trustworthy live demonstration; they layer onto the happy-path round-trip from US1.

**Independent Test**: Point the chat endpoint at the Ollama provider with the server stopped (or the model
absent) and confirm a readable 503; simulate a slow provider past the timeout and confirm a readable 504;
send an empty messages array and confirm 400; send a conversation whose last message is not a user turn and
confirm 400; confirm the session id is echoed back in every error response. Swap in the stub provider and
confirm the same endpoint completes a deterministic round-trip with no network.

**Acceptance Scenarios**:

1. **Given** the chat endpoint configured with the real provider, **When** the LLM is unreachable or its
   model is missing, **Then** the endpoint returns a readable 503 and preserves the session id.
2. **Given** the chat endpoint configured with the real provider, **When** the LLM call exceeds the timeout,
   **Then** the endpoint returns a readable 504 and preserves the session id.
3. **Given** an empty messages array, **When** it is sent to the chat endpoint, **Then** the endpoint returns
   400 before any LLM call.
4. **Given** a conversation whose last message is not a user turn, **When** it is sent, **Then** the endpoint
   returns 400 before any LLM call.
5. **Given** the deterministic stub provider, **When** a round-trip test runs, **Then** it completes with no
   network access and a reproducible result.
6. **Given** the provider port abstraction, **When** a new provider is later added, **Then** the pipeline and
   chat endpoint require no change to consume it (Constitution IV).

---

### Edge Cases

- **Earlier assistant message carries PII**: a later turn resends an already-de-pseudonymized assistant
  message → every original in the whole history is re-pseudonymized consistently before the LLM call.
- **Unforeseen inflection of a fake name**: the LLM renders a fake PERSON/LOCATION in a case the form table
  missed → fuzzy fallback restores the original in base form (documented limitation: grammar may be slightly
  off, identity is correct).
- **Inflected fake identifier**: a fake PESEL/NIP/REGON/bank account, e-mail or phone appears altered →
  exact-only, fuzzy never fires; if the exact pass cannot match it, it is left as-is rather than guessed.
- **Invented name**: the LLM produces a name that was never in the input → left untouched (prefix anchor
  prevents accidental fuzzy restoration).
- **Short token**: a candidate token under 4 characters → never fuzzy-matched.
- **Prefix mismatch**: a candidate that does not share the required common prefix with any stored fake →
  not matched, even if edit distance alone would be small.
- **Unresolvable tie**: two stored fakes match a candidate equally well → skip, never guess.
- **Already-restored span**: a span the exact pass restored → never re-touched by the fuzzy pass.
- **Empty messages array**: returns 400 before any LLM call.
- **Last message not a user turn**: returns 400 before any LLM call.
- **LLM unreachable / missing model**: returns 503 with a readable message; session id preserved.
- **LLM timeout**: returns 504 with a readable message; session id preserved.
- **Absent/blank session id**: a new session is started and its id is returned.
- **No PII in the request**: the round-trip still works; the messages sent to the LLM equal the input and the
  answer is returned unchanged (nothing to restore).

## Requirements *(mandatory)*

### Functional Requirements

#### Anonymization pipeline orchestrator

- **FR-001**: The system MUST provide a reusable anonymization pipeline with two stages — **inbound**
  (pseudonymize) and **outbound** (de-pseudonymize) — that is callable programmatically as an internal
  component, not only through an HTTP handler, so the chat endpoint and later epics can consume it directly.
- **FR-002**: The inbound stage MUST reuse the EPIC 2 detection layer and the EPIC 3 generator + reversible
  mapping store to detect PII, substitute session-consistent realistic fakes, and persist the mapping. It
  MUST NOT reimplement detection, generation, or storage.
- **FR-003**: The substitution orchestration that currently lives inline in the EPIC 3 debug handlers MUST be
  extracted into the shared pipeline so the same inbound/outbound logic backs both the existing debug
  endpoints and the new chat endpoint. The existing debug endpoints' observable behaviour and wire format
  MUST be preserved (the EPIC 3 test suite and the Redis/encryption formats remain the regression contract).
- **FR-004**: The outbound stage MUST restore originals in the LLM's answer using the EPIC 3 exact +
  inflection restore **first**, then the bounded fuzzy fallback (FR-009–FR-015) only as a fallback.

#### Multi-turn history handling

- **FR-005**: In chat mode the inbound stage MUST pseudonymize **every message in the conversation array**
  on every turn — including earlier assistant messages that were previously de-pseudonymized for display —
  not only the last message, so no original ever reaches the LLM.
- **FR-006**: Re-pseudonymizing content already seen in the session MUST be deterministic — the same original
  MUST map to the same fake it was assigned earlier in the session (session consistency from EPIC 3).
- **FR-007**: The client↔gateway hop is inside the trust boundary and is NOT protected; only the
  gateway↔LLM hop is. The assistant's answer returned to the caller MUST be de-pseudonymized (originals in
  place) for display, even though it will be re-pseudonymized on the next turn.

#### Fuzzy fallback on the outbound stage

- **FR-008**: The fuzzy fallback MUST run **only as a fallback** on tokens the exact + inflection pass did not
  already replace, and MUST never touch an already-restored span.
- **FR-009**: The fuzzy fallback MUST be scoped by an **allowlist** of exactly **`{PERSON, LOCATION}`**;
  **every other entity type is exact-only** and MUST never be fuzzy-matched. The exact-only set therefore
  includes the structured identifiers and contact/temporal types under their real detector labels —
  `PESEL`, `NIP`, `REGON`, `IBAN`/`POLISH_BANK_ACCOUNT`, `NRB`, `EMAIL_ADDRESS`, `PHONE_NUMBER`,
  `DATE_TIME`, `POLISH_ADDRESS`, `ORGANIZATION` — and any future type by default (a one-character edit on a
  PESEL is a different, valid-looking number). The allowlist framing is deliberate so a new entity type is
  exact-only until explicitly admitted to fuzzy.
- **FR-010**: The fuzzy fallback MUST operate at the **token level on word boundaries** with a **minimum
  token length of 4** characters; shorter tokens MUST NOT be matched.
- **FR-011**: Before a match is accepted, a candidate token and a stored fake token MUST share a common
  **prefix of roughly ≥ 60% of the shorter token's length** (the prefix anchor), because Polish inflection
  changes the suffix, not the stem.
- **FR-012**: A **length-aware bounded edit distance (≤ 2)** MUST be the final distance gate applied after
  the prefix anchor; candidates beyond the gate MUST NOT be matched.
- **FR-013**: The best match MUST be deterministic; on an **unresolvable tie** the token MUST be skipped
  (never guessed).
- **FR-014**: On a fuzzy hit the original MUST be restored in its **base (nominative) form** — a documented
  limitation: identity is restored correctly even if the surrounding grammar is slightly off.
- **FR-015**: A name absent from the input (invented by the LLM) MUST be left untouched; the prefix anchor
  MUST prevent accidental fuzzy restoration.

#### LLM provider port

- **FR-016**: The system MUST define a **minimal abstract provider interface**: send a messages array → an
  assistant text reply, plus a reachability check. The pipeline MUST depend on this interface, not on any
  concrete provider (Constitution IV).
- **FR-017**: The system MUST provide **one concrete provider** that talks to a **local Ollama** server over
  REST and implements the interface.
- **FR-018**: The system MUST provide a deterministic, **network-free echo/stub provider** implementing the
  same interface so pipeline round-trip tests are fast and reproducible.
- **FR-019**: Adding a future provider MUST NOT require modifying the pipeline or the chat endpoint
  (Constitution IV). The full provider line-up and model-based routing are out of scope for this epic.

#### Chat endpoint

- **FR-020**: The system MUST expose a minimal **`POST /v1/chat/completions`** endpoint, OpenAI-compatible in
  shape, that accepts a **messages array**, an **optional session id**, and an **optional model name**
  (defaulting to the configured model when absent), runs inbound → LLM → outbound, and returns the
  **assistant's answer** plus the **session id**.
- **FR-021**: The endpoint MUST return **400** when the messages array is empty or when the last message is
  not a user turn, **before** any LLM call.
- **FR-022**: The endpoint MUST return **503** when the LLM is unreachable or missing its model and **504**
  when the LLM call times out, each with a readable message, and MUST preserve the session id in the error
  response.
- **FR-023**: An absent or blank session id MUST start a new session, and the chosen/generated id MUST be
  returned in the response.

#### Cross-cutting (unchanged from EPIC 3 and the constitution)

- **FR-024**: No original personal data MUST ever appear in logs or in any outgoing request to the LLM — only
  synthetic values reach the provider, and logs carry only non-identifying metadata (session id, entity
  types/counts, timings, status/error codes) (Constitution VIII, I).
- **FR-025**: The flow MUST be **synchronous** (request-response); the full LLM answer MUST be received
  before de-pseudonymization begins. Streaming/SSE is a deliberate non-goal (Constitution V).
- **FR-026**: Reversibility, AES-256-at-rest mapping, the session TTL, and the no-PII-in-logs rule from
  EPIC 3 MUST be honoured unchanged.
- **FR-027**: The pipeline round-trip (via the stub provider), multi-turn deterministic re-pseudonymization,
  the fuzzy fallback positive and negative cases (PERSON/LOCATION restored in base form; identifier/e-mail/
  phone never fuzzy; already-restored span untouched; invented name untouched; tie skipped), and the endpoint
  error paths (400 / 503 / 504 with session id preserved) MUST each be covered by tests that run without
  network access.

### Key Entities *(include if feature involves data)*

- **Anonymization pipeline**: The reusable orchestrator with an inbound (pseudonymize) and an outbound
  (de-pseudonymize) stage. Inbound composes EPIC 2 detection + EPIC 3 generation/store; outbound composes the
  EPIC 3 exact + inflection restore followed by the fuzzy fallback. Callable programmatically by the chat
  endpoint and later epics.
- **Conversation / messages array**: The chat request payload — an ordered list of role-tagged messages
  (user/assistant/…) plus an optional session id. The whole array is pseudonymized each turn; the last
  message must be a user turn.
- **LLM provider port**: The abstract interface (send messages → assistant text; reachability check) that
  decouples the pipeline from any concrete provider. Concrete realizations in this epic: a **local Ollama
  REST provider** and a deterministic **echo/stub provider** for tests.
- **Fuzzy restorer**: The bounded, conservative outbound fallback that recovers unforeseen inflected forms of
  fake PERSON/LOCATION tokens — token-level, word-boundary, min length 4, prefix-anchored, edit-distance
  gated, deterministic, restoring the original in base form and skipping on ambiguity.
- **Chat response**: The endpoint's minimal reply — the de-pseudonymized assistant answer plus the session
  id. The full response contract (anonymization metadata, finish_reason passthrough) is a later epic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can send a single-turn Polish request containing a person, a city and at least one
  structured identifier to the chat endpoint and receive a coherent answer with the originals restored in
  place, while the messages handed to the LLM contained only synthetic values.
- **SC-002**: In a multi-turn conversation, every original across the whole resent history — including
  originals re-entering through an earlier assistant message — is replaced before the LLM call, and each
  original maps to the same fake it received earlier in the session.
- **SC-003**: When the LLM inflects a fake PERSON or LOCATION in a form the exact + inflection pass missed,
  the original is restored in its base (nominative) form; when it inflects a fake identifier, e-mail or
  phone, the fuzzy fallback does not fire.
- **SC-004**: A name the input never contained is left untouched in the LLM's answer (no accidental fuzzy
  restoration); an already-restored span is never re-touched; an unresolvable tie is skipped.
- **SC-005**: The same chat endpoint completes a deterministic, network-free round-trip when backed by the
  stub provider and a live round-trip when backed by the local Ollama provider, with no change to the
  pipeline.
- **SC-006**: The endpoint returns 400 for an empty messages array or a non-user last message (before any LLM
  call), 503 when the LLM is unreachable or missing its model, and 504 on timeout — each with a readable
  message and the session id preserved.
- **SC-007**: No original personal data appears in logs or in any outgoing request to the LLM in any of the
  above flows.
- **SC-008**: The EPIC 3 debug endpoints continue to pass their existing tests after the substitution
  orchestration is extracted into the shared pipeline (no behaviour, API, or wire-format change).
- **SC-009**: The pipeline round-trip, multi-turn determinism, fuzzy positive/negative cases, and the
  endpoint error paths are each covered by passing tests that run without network access.

## Assumptions

- **Layer boundary**: This epic delivers the pipeline orchestrator, the fuzzy fallback, one real provider
  behind a port (plus a stub), and the minimal chat endpoint. Detection (EPIC 2) and generation + the
  reversible store (EPIC 3) are **reused**, not reimplemented. The OpenAI/Anthropic adapters and model-based
  router, the full chat response contract, logging/metrics middleware, the session GET/DELETE endpoints, and
  streaming/SSE are explicitly **later epics**. The standalone no-LLM `POST /v1/anonymize` is **dropped** —
  EPIC 3's `POST /v1/pseudonymize` covers it.
- **Message roles pseudonymized**: "Every message in the array" means the textual content of every message
  regardless of role (user, assistant, and any system message) is run through the inbound stage each turn,
  since the protected boundary is the gateway↔LLM hop. The precise handling of non-text/structured message
  parts is a plan-phase detail.
- **Outbound restores the answer only**: The outbound stage de-pseudonymizes the LLM's assistant answer
  returned to the caller; the caller already holds the originals for its own prior turns (client↔gateway is
  trusted), so the gateway returns just the assistant's answer plus the session id.
- **Error-code mapping**: Timeout → **504**; unreachable or missing model → **503**; malformed request
  (empty array / non-user last message) → **400**. Validation that can be decided without the LLM happens
  before any LLM call. The exact timeout value and Ollama base URL/model name come from configuration
  (consistent with EPIC 1 settings) and are plan-phase details.
- **Prefix-anchor threshold**: "Roughly ≥ 60% of the shorter token's length" is the design intent for the
  shared-prefix gate; the exact rounding/length-aware tie-in with the edit-distance bound (≤ 2) is a
  plan-phase detail, kept conservative so identifiers/e-mail/phone are never reached and invented names are
  not restored.
- **Base-form restoration limitation**: A fuzzy hit restores the original in nominative/base form by design
  (Constitution IX); the surrounding grammar may be slightly off. This is an accepted, documented limitation,
  consistent with EPIC 3's pragmatic inflection stance.
- **Session id handling**: As in EPIC 3, an absent/blank session id starts a fresh session and the
  chosen/generated id is returned; the id format/generation strategy is a plan-phase detail. The chat
  endpoint depends on Redis (the store) and is therefore subject to the EPIC 1 Redis-availability gate; it
  also depends on the detection model.
- **Provider scope**: Exactly **one** real provider (local Ollama over REST) is wired in this epic behind the
  port, alongside the deterministic stub. The port exposes a lightweight **reachability check** that is
  implemented and tested this epic but **not yet consumed**: the 503 unreachable/missing-model path is driven
  by the `complete()` call raising a provider error, and the reachability check is **reserved for the future
  `/health` integration**. The full provider line-up and model-based routing are a later epic — the
  configured default-provider setting is **not consulted** here (the endpoint talks to Ollama directly).
- **No performance target**: No latency/throughput SLA is defined for this epic; large-document handling and
  performance tuning are out of scope. Synchronous request-response only (Constitution V).
- **Trusted demo context**: The chat endpoint is exercised in a trusted/development context for the thesis
  demonstration; authentication and hardened exposure controls are out of scope for this epic, but the
  no-PII-in-logs and no-PII-to-provider rules (FR-024) still hold without exception (Constitution I, VIII).
