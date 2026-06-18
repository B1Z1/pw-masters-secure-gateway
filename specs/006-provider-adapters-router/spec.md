# Feature Specification: EPIC 5 — Provider Adapters (Provider-Agnostic) and a Model-Based Provider Router

**Feature Branch**: `006-provider-adapters-router`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "EPIC 5 — LLM provider adapters (provider-agnostic) and a model-based provider router. Generalize the single-provider slice from EPIC 4 into a real provider-agnostic layer: more than one concrete LLM provider behind the existing abstract provider port, and a router that picks the right provider per request from the requested model — without the pipeline or the chat endpoint ever knowing which concrete provider is in play."

## Overview

EPIC 4 closed the first end-to-end round-trip through a real LLM, but only against **one** provider
(local Ollama), wired in directly: the provider factory returns Ollama unconditionally and ignores the
requested model entirely. Provider agnosticism is a core principle of this system (Constitution IV), so
the gateway must support **more than one** real provider and choose between them at request time through
**one stable interface**.

This epic generalizes that single-provider slice into a real provider-agnostic layer. It adds an
**OpenAI adapter** and an **Anthropic adapter** behind the **same** abstract provider port introduced in
EPIC 4, formalizes that port (it is reused unchanged), keeps the **Ollama adapter** but selects it
**explicitly** rather than as a silent default, and introduces a **model-based router** that picks the
adapter from the request's model. The router is itself an implementation of the provider port (a
composite): the chat endpoint keeps calling exactly one provider, and the router dispatches per request
internally. After this epic, adding or swapping a provider is a **configuration and adapter concern
only** — the pipeline and the chat endpoint do not change.

Routing is by **model prefix**, not by a registry of valid model names: a model starting with `gpt-`
goes to OpenAI, `claude-` to Anthropic, and `ollama/…` to Ollama (with the `ollama/` prefix stripped
before the name is sent on, so `ollama/qwen2.5:3b` reaches Ollama as `qwen2.5:3b`). Any other model is a
**client error** (400, listing the recognized prefixes) — Ollama is deliberately **not** a catch-all. A
request that supplies **no model** falls back to the configured **default model**, which is a local
Ollama model so the keyless, offline demo keeps working out of the box; the default's own prefix then
selects the provider by the same rules.

The epic also **extends and centralizes the provider-error taxonomy**. Beyond EPIC 4's unreachable /
missing-model / timeout, adapters must surface a **rate limit** (the provider returned 429 upstream —
the adapter does not retry; the endpoint returns 429) and a **missing/invalid API key** for the selected
provider (an auth/configuration error the endpoint returns as 503, naming **which** key is missing). API
keys remain **optional at startup** — the error appears only on first use of a provider that needs one.
The mapping from each error kind to its HTTP status stays in **one place**.

The whole-history pseudonymization guarantee from EPIC 4 is unchanged: every outgoing provider request —
**for any provider** — contains only synthetic data, and no original personal data appears in logs. The
EPIC 3/EPIC 4 reversibility, AES-256 mapping, session TTL, and no-PII-in-logs guarantees hold for every
provider without exception.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route each request to the right provider by its model (Priority: P1)

A reviewer (or developer) sends chat requests with different models in one unchanged flow. A request
with model `gpt-4o` is served by the OpenAI adapter; `claude-3-5-sonnet` by the Anthropic adapter; and
`ollama/qwen2.5:3b` by the Ollama adapter — and Ollama receives the bare name `qwen2.5:3b`, without the
`ollama/` prefix. The chat endpoint and the anonymization pipeline are identical across all three; only
the configured router decides where the (already pseudonymized) messages go.

**Why this priority**: This is the headline deliverable of the epic — multiple concrete providers behind
one stable interface, chosen per request from the model. Without it there is no provider agnosticism in
practice; everything else in the epic layers onto this routing.

**Independent Test**: With each provider replaced by a recording test double, send three requests
(`gpt-4o`, `claude-3-5-sonnet`, `ollama/qwen2.5:3b`) through the chat endpoint and confirm each request
reached the matching adapter, that the Ollama adapter received `qwen2.5:3b` (prefix stripped), and that
neither the endpoint nor the pipeline needed any change to support the three providers.

**Acceptance Scenarios**:

1. **Given** a request with model `gpt-4o`, **When** it is processed, **Then** the router dispatches it
   to the OpenAI adapter and to no other provider.
2. **Given** a request with model `claude-3-5-sonnet`, **When** it is processed, **Then** the router
   dispatches it to the Anthropic adapter and to no other provider.
3. **Given** a request with model `ollama/qwen2.5:3b`, **When** it is processed, **Then** the router
   dispatches it to the Ollama adapter and the name handed to Ollama is `qwen2.5:3b` (the `ollama/`
   prefix is stripped).
4. **Given** the chat endpoint and pipeline from EPIC 4, **When** the router is introduced as what the
   provider factory returns, **Then** neither the endpoint nor the pipeline is modified to support the
   new providers (Constitution IV).

---

### User Story 2 - Unknown or absent model is handled predictably (Priority: P1)

A request that names a model matching no recognized prefix is rejected as a **client error** before
anything is sent to any provider — the response is a 400 whose message lists the recognized prefixes. A
request that names **no model** falls back to the configured default model (a local Ollama model), which
is then routed by its own prefix. Ollama is never a silent catch-all for unrecognized models.

**Why this priority**: Predictable routing edges are part of the core routing contract: an unrecognized
model must fail loudly as the caller's mistake, and the keyless offline demo must keep working when no
model is supplied. Both are required for the router to be trustworthy and are independently demonstrable.

**Independent Test**: Send a request with model `mistral-large` (no recognized prefix) and confirm a 400
whose message lists `gpt-`, `claude-`, and `ollama/`, and that no provider was contacted. Then send a
request with no model field and confirm it is routed to the Ollama adapter via the configured default
model.

**Acceptance Scenarios**:

1. **Given** a request whose model matches none of the recognized prefixes, **When** it is processed,
   **Then** the endpoint returns 400 with a message listing the recognized prefixes and nothing is sent
   to any provider.
2. **Given** a request with no model supplied, **When** it is processed, **Then** the configured default
   model is used and the request is routed by that default's prefix.
3. **Given** the configured default model is a local Ollama model, **When** a no-model request is
   processed with no API keys configured, **Then** the request still completes through the Ollama adapter
   (the offline demo keeps working out of the box).

---

### User Story 3 - Anthropic adapter converts messages to Anthropic's contract (Priority: P2)

The system's native message shape is OpenAI-style (a flat array of role-tagged messages, system
included). Anthropic's rules differ, so the Anthropic adapter converts the messages before the call:
system content is lifted out of the message list into Anthropic's separate top-level system field
(multiple system messages concatenated; omitted entirely when there is none); the remaining conversation
must begin with a user turn and alternate user/assistant, so two consecutive same-role messages are
merged into one; and every call carries an explicit maximum-output-tokens value taken from
configuration.

**Why this priority**: Anthropic is one of the two new providers and its message contract is the most
involved transformation in the epic. The OpenAI adapter needs no conversion (native shape) and Ollama is
reused, so the Anthropic conversion is the adapter-specific correctness work that most warrants its own
verified slice. It builds on the routing from US1.

**Independent Test**: Hand the Anthropic adapter a messages array containing a system message and two
consecutive user messages, with the Anthropic client replaced by a recording double; confirm the
outgoing call places the system content in the top-level system field, presents a history that starts
with a user turn and alternates (the two consecutive user messages merged into one), and includes an
explicit maximum-output-tokens value.

**Acceptance Scenarios**:

1. **Given** a messages array containing one or more system messages, **When** the Anthropic adapter
   builds the call, **Then** the system content is placed in Anthropic's top-level system field
   (multiple system messages concatenated) and is not present as a message role.
2. **Given** a messages array with no system content, **When** the Anthropic adapter builds the call,
   **Then** the top-level system field is omitted.
3. **Given** a messages array with two consecutive messages of the same role, **When** the Anthropic
   adapter builds the call, **Then** those messages are merged into one so the history alternates
   user/assistant and begins with a user turn.
4. **Given** any Anthropic call, **When** it is built, **Then** it carries an explicit
   maximum-output-tokens value sourced from configuration.

---

### User Story 4 - OpenAI adapter behaviours (native shape, truncation, model errors) (Priority: P2)

Because OpenAI's message format is the system's native shape, the OpenAI adapter performs no conversion:
a system message is passed through as the first message. When an answer is cut off by the token limit
(the provider reports a length finish reason), the adapter logs a warning and still returns the partial
content rather than failing. When the caller requests a deprecated or otherwise unknown model that slips
past prefix routing, the adapter surfaces the provider's own error to the caller rather than masking it.

**Why this priority**: The OpenAI adapter is the second new provider and its three documented behaviours
(native passthrough, graceful truncation, error surfacing) are the verifiable contract of that adapter.
It depends on routing from US1 but is independently testable with a recording/mock client.

**Independent Test**: With the OpenAI client replaced by a double, confirm a system message is sent as
the first message unchanged; confirm a length-truncated response produces a logged warning and still
returns the partial content; and confirm a deprecated/unknown model causes the provider's own error to
reach the caller.

**Acceptance Scenarios**:

1. **Given** a messages array whose first message is a system message, **When** the OpenAI adapter builds
   the call, **Then** the system message is passed through as the first message with no conversion.
2. **Given** a provider response with a length finish reason (truncated by the token limit), **When** the
   adapter handles it, **Then** a warning is logged and the partial content is still returned to the
   caller.
3. **Given** a deprecated or unknown model that reaches the OpenAI adapter, **When** the call is made,
   **Then** the provider's own error is surfaced to the caller (no silent substitution or masking).

---

### User Story 5 - Provider errors map to predictable statuses (rate limit, missing key) (Priority: P2)

The provider-error taxonomy is extended and stays centralized. When a provider returns a rate limit
(429 upstream), the adapter does **not** retry; it raises a rate-limit error that the endpoint returns to
the client as 429. When the selected provider's API key is missing or invalid, the adapter raises an
auth/configuration error that the endpoint returns as 503, with a readable message naming **which** key
is missing. API keys stay optional at startup, so this error appears only on first use of a provider that
needs one. Every error-kind-to-status decision lives in one place.

**Why this priority**: Trustworthy failure behaviour is required for a live demo against hosted
providers: a rate limit must be reported as such without silent retries, and a missing key must produce a
clear, actionable message rather than a generic crash. It layers onto the adapters from US3/US4.

**Independent Test**: Simulate a provider returning a rate limit and confirm the endpoint returns 429
with no retry attempted. Configure no key for a hosted provider, send a request that routes to it, and
confirm a 503 whose message names the missing key — while startup with no keys still succeeds.

**Acceptance Scenarios**:

1. **Given** a selected provider that returns a rate limit (429 upstream), **When** the call is made,
   **Then** the adapter does not retry and the endpoint returns 429 to the client.
2. **Given** a selected provider whose API key is not configured, **When** a request routes to it, **Then**
   the endpoint returns 503 with a readable message naming the missing key.
3. **Given** the gateway starts with no provider API keys configured, **When** the process starts, **Then**
   startup succeeds and the missing-key error appears only on first use of a provider that needs a key.
4. **Given** the full set of error kinds (unreachable, missing model, timeout, rate limit, missing key,
   unknown model), **When** each occurs, **Then** the HTTP status it maps to is decided in a single
   centralized place.

---

### User Story 6 - Ollama reused and selected explicitly, edge cases intact (Priority: P3)

The Ollama adapter from EPIC 4 is reused unchanged in behaviour but is now selected **explicitly** by
the `ollama/` prefix rather than as a silent default. Its existing edge cases still stand: the server
being unreachable, the model not being pulled, and a separately-configurable long timeout for slow local
models.

**Why this priority**: This is continuity work — the value is preserving EPIC 4's working local provider
while it becomes one of several explicitly-routed adapters. It is lower priority than the new providers
and the router because nothing about Ollama's own behaviour changes; only how it is selected does.

**Independent Test**: Route a request with `ollama/qwen2.5:3b` and confirm it reaches the Ollama adapter
explicitly (not via a fallback). With the Ollama server stopped confirm a 503; with the model absent
confirm a 503; and confirm the Ollama timeout is its own configurable value, distinct from any hosted
provider's behaviour.

**Acceptance Scenarios**:

1. **Given** a request with an `ollama/`-prefixed model, **When** it is processed, **Then** it reaches
   the Ollama adapter because the prefix matched explicitly, not because Ollama is a fallback.
2. **Given** the Ollama server is unreachable or the model is not pulled, **When** an `ollama/` request
   is processed, **Then** the endpoint returns 503 with a readable message (EPIC 4 behaviour preserved).
3. **Given** a slow local model, **When** the Ollama call exceeds its separately-configurable long
   timeout, **Then** the endpoint returns 504 — and that timeout is configured independently of hosted
   providers.

---

### Edge Cases

- **`gpt-` model** → routed to the OpenAI adapter; no message conversion; system message sent first.
- **`claude-` model** → routed to the Anthropic adapter; system lifted to the top-level field; history
  begins with user and alternates; explicit max-output-tokens.
- **`ollama/…` model** → routed to the Ollama adapter; the `ollama/` prefix is stripped before the name
  is sent (e.g. `ollama/qwen2.5:3b` → `qwen2.5:3b`).
- **Unrecognized model prefix** → 400 listing the recognized prefixes; nothing sent to any provider
  (Ollama is not a catch-all).
- **No model supplied** → the configured default model is used and routed by its prefix; the default is a
  local Ollama model so the keyless offline demo works.
- **Multiple system messages (Anthropic)** → concatenated into the single top-level system field.
- **No system content (Anthropic)** → the top-level system field is omitted.
- **Two consecutive same-role messages (Anthropic)** → merged into one so the history alternates.
- **Length-truncated answer (OpenAI)** → a warning is logged and the partial content is still returned.
- **Deprecated/unknown model reaching a provider** → the provider's own error is surfaced to the caller.
- **Provider rate limit (429 upstream)** → no retry; endpoint returns 429.
- **Missing/invalid API key for the selected provider** → endpoint returns 503 naming the missing key;
  startup with no keys still succeeds.
- **Ollama unreachable / model not pulled** → 503 (EPIC 4 behaviour preserved).
- **Ollama slow model past its long timeout** → 504, using a separately-configurable timeout.
- **No PII anywhere** → for every provider, the outgoing request carries only synthetic data and no
  original personal data appears in logs.

## Requirements *(mandatory)*

### Functional Requirements

#### Abstract provider port (reused and formalized)

- **FR-001**: The system MUST reuse the EPIC 4 abstract provider port **unchanged** — one asynchronous
  call that takes an OpenAI-shaped messages array plus a model and returns the assistant's text, plus a
  lightweight reachability check — and its OpenAI-compatible message unit. Every adapter in this epic
  MUST implement this same port.
- **FR-002**: No component outside the adapters (the pipeline, the chat endpoint, the router's callers)
  MAY know any concrete provider; they depend only on the abstract port (Constitution IV).

#### OpenAI adapter

- **FR-003**: The system MUST provide an OpenAI adapter, using the official OpenAI client, that
  implements the provider port and serves models whose name starts with `gpt-`.
- **FR-004**: Because the OpenAI message format is the system's native shape, the OpenAI adapter MUST
  perform **no** message conversion; a system message MUST be passed through as the first message.
- **FR-005**: When an answer is truncated by the token limit (the provider reports a length finish
  reason), the OpenAI adapter MUST log a warning and STILL return the partial content.
- **FR-006**: A deprecated or unknown model reaching the OpenAI adapter MUST surface the provider's own
  error to the caller (no pre-validation by a model-name registry, no masking).

#### Anthropic adapter

- **FR-007**: The system MUST provide an Anthropic adapter, using the official Anthropic client, that
  implements the provider port and serves models whose name starts with `claude-`.
- **FR-008**: The Anthropic adapter MUST lift system content out of the message list into Anthropic's
  separate top-level system field: multiple system messages MUST be concatenated, and when there is no
  system content the field MUST be omitted entirely (system MUST NOT be sent as a message role).
- **FR-009**: The Anthropic adapter MUST present a conversation that begins with a user turn and
  alternates user/assistant; two consecutive messages with the same role MUST be merged into one.
- **FR-010**: The Anthropic adapter MUST include an explicit maximum-output-tokens value on every call,
  sourced from configuration.

#### Ollama adapter (reused)

- **FR-011**: The system MUST reuse the EPIC 4 Ollama adapter, now selected **explicitly** by the
  `ollama/` prefix (not as a silent default), with the `ollama/` prefix stripped before the model name is
  sent to Ollama (e.g. `ollama/qwen2.5:3b` calls Ollama with `qwen2.5:3b`).
- **FR-012**: The Ollama adapter's existing edge cases MUST stand unchanged: server unreachable, model
  not pulled, and a separately-configurable long timeout for slow local models.

#### Model-based provider router

- **FR-013**: The system MUST provide a model-based provider router that is itself an implementation of
  the provider port (a composite). The chat endpoint MUST keep calling exactly one provider; the router
  MUST dispatch per request internally from the model.
- **FR-014**: The router MUST route by model prefix: `gpt-` → OpenAI adapter; `claude-` → Anthropic
  adapter; `ollama/` → Ollama adapter (prefix stripped). Routing MUST be by prefix only — there is no
  registry/allowlist of valid model names per provider.
- **FR-015**: A model matching none of the recognized prefixes MUST result in a 400 "unknown model"
  error whose message lists the recognized prefixes, and nothing MUST be sent to any provider. Ollama
  MUST NOT be a catch-all for unrecognized models.
- **FR-016**: A request with no model supplied MUST fall back to the configured default model, whose own
  prefix then selects the provider by the same rules.
- **FR-017**: The configured default model MUST be a local Ollama model so the keyless, offline demo
  keeps working out of the box.
- **FR-018**: The router MUST become what the provider factory returns, replacing the hardcoded single
  provider from EPIC 4, with no change to the pipeline or the chat endpoint (Constitution IV).

#### Centralized provider-error taxonomy

- **FR-019**: The provider-error taxonomy MUST be extended beyond EPIC 4's unreachable / missing-model /
  timeout to also cover a **rate limit** and a **missing/invalid API key**.
- **FR-020**: On a provider rate limit (429 upstream), the adapter MUST NOT retry; it MUST raise a
  rate-limit error that the endpoint returns to the client as **429**.
- **FR-021**: On a missing or invalid API key for the selected provider, the adapter MUST raise an
  auth/configuration error that the endpoint returns as **503**, with a readable message naming WHICH key
  is missing.
- **FR-022**: Provider API keys MUST remain optional at startup; the missing-key error MUST appear only
  on first use of a provider that needs one (startup with no keys MUST succeed).
- **FR-023**: The mapping from each error kind to its HTTP status (unreachable/missing-model → 503,
  timeout → 504, rate limit → 429, missing/invalid key → 503, unknown model → 400) MUST live in a single
  centralized place.

#### Cross-cutting (unchanged from EPIC 3/EPIC 4 and the constitution)

- **FR-024**: The whole-history pseudonymization guarantee MUST be unchanged: every outgoing provider
  request — **for any provider** — MUST contain only synthetic data, and no original personal data MUST
  appear in logs (Constitution I, VIII).
- **FR-025**: The flow MUST remain synchronous (request-response); the full answer MUST be received
  before de-pseudonymization. Streaming/SSE remains a deliberate non-goal (Constitution V).
- **FR-026**: Reversibility, the AES-256-at-rest mapping, the session TTL, and the no-PII-in-logs rule
  from EPIC 3/EPIC 4 MUST hold for **every** provider without exception.
- **FR-027**: Routing per prefix (`gpt-`/`claude-`/`ollama/`, including `ollama/` stripping), the
  unknown-model 400 and no-model default fallback, the Anthropic message conversion (system lifted,
  alternation/merge, explicit max-output-tokens), the OpenAI behaviours (system passthrough, length-
  truncation warning + partial content), the error mapping (429 rate limit without retry, 503 named
  missing key), and the no-PII guarantee MUST each be covered by tests that run without network access
  (provider clients replaced by test doubles/mocks).

### Key Entities *(include if feature involves data)*

- **Provider port**: The abstract interface reused unchanged from EPIC 4 — send an OpenAI-shaped messages
  array + a model → assistant text, plus a lightweight reachability check. The single contract every
  adapter and the router implement; the decoupling point that keeps the pipeline/endpoint provider-
  agnostic.
- **OpenAI adapter**: A concrete provider for `gpt-` models using the official OpenAI client; native
  message shape (no conversion); logs a warning and returns partial content on length truncation;
  surfaces the provider's own error for deprecated/unknown models.
- **Anthropic adapter**: A concrete provider for `claude-` models using the official Anthropic client;
  converts OpenAI-shaped messages to Anthropic's contract (system lifted to a top-level field;
  user-first alternation with consecutive same-role merge; explicit max-output-tokens from config).
- **Ollama adapter**: The EPIC 4 local provider, reused, now selected explicitly by the `ollama/` prefix
  (stripped before send); long, separately-configurable timeout; unreachable/missing-model edge cases
  preserved.
- **Provider router**: The composite implementation of the provider port that dispatches each request to
  one adapter by model prefix, returns a 400 for unrecognized models, and applies the configured default
  model when none is supplied. It is what the provider factory returns.
- **Provider-error taxonomy**: The centralized set of error kinds (unreachable, missing model, timeout,
  rate limit, missing/invalid key, unknown model) and the single mapping from each to its HTTP status
  (503 / 503 / 504 / 429 / 503 / 400).
- **Provider configuration**: The settings that drive routing and adapters — the optional per-provider
  API keys, the default model (a local Ollama model), the Anthropic maximum-output-tokens value, and the
  Ollama base URL and long timeout. Keys are optional at startup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A request with model `gpt-4o` reaches the OpenAI adapter, one with `claude-3-5-sonnet`
  reaches the Anthropic adapter, and one with `ollama/qwen2.5:3b` reaches the Ollama adapter with the
  name `qwen2.5:3b` — all through the same unchanged endpoint and pipeline.
- **SC-002**: A request whose model matches no recognized prefix returns 400 with a message listing the
  recognized prefixes, and nothing is sent to any provider.
- **SC-003**: A request with no model is routed via the configured default model, and that default routes
  to a local Ollama provider so the request completes with no API keys configured.
- **SC-004**: For an Anthropic call built from a messages array containing a system message and two
  consecutive user messages, the outgoing call places the system content in the top-level system field,
  presents a history that begins with a user turn and alternates (the consecutive user messages merged),
  and carries an explicit maximum-output-tokens value.
- **SC-005**: An OpenAI answer truncated by the token limit yields a logged warning and the partial
  content is still returned; a deprecated/unknown OpenAI model surfaces the provider's own error.
- **SC-006**: A provider rate limit results in a 429 to the client with no retry attempted; a request
  routed to a provider whose API key is not configured results in a 503 whose message names the missing
  key; and the gateway starts successfully with no API keys configured.
- **SC-007**: Adding or swapping a provider after this epic requires only a new/changed adapter and
  configuration — no change to the pipeline or the chat endpoint.
- **SC-008**: For every provider, the messages handed to the provider contain only synthetic values and
  no original personal data appears in logs (Constitution I, VIII).
- **SC-009**: The routing, Anthropic conversion, OpenAI behaviours, error-status mapping, and no-PII
  guarantees above are each covered by passing tests that run without network access.

## Assumptions

- **Layer boundary**: This epic delivers the OpenAI and Anthropic adapters, the explicit reuse of the
  Ollama adapter, and the model-based router behind the EPIC 4 provider port — which is reused unchanged.
  The pipeline (EPIC 4) and the detection/generation/store layers (EPIC 2/EPIC 3) are **reused**, not
  modified. Streaming/SSE, the full chat response contract (usage, finish_reason passthrough,
  anonymization metadata), a per-provider `/health` endpoint, the session GET/DELETE endpoints, a
  per-provider model-name allowlist, and automatic retries/backoff are explicitly **out of scope** (later
  epics or deliberate non-goals).
- **Routing is by prefix only**: There is intentionally no registry of valid model names per provider.
  A model name that carries a recognized prefix but is not actually offered by that provider (e.g. a
  deprecated `gpt-…`) is allowed to reach the provider, which then surfaces its own error — rather than
  being rejected up front. The recognized prefixes are `gpt-`, `claude-`, and `ollama/`.
- **Default model changes to a local Ollama model**: EPIC 4 shipped a default model whose prefix is not
  an Ollama model. This epic changes the configured default to an `ollama/`-prefixed local model (the
  documented local default is `ollama/qwen2.5:3b`) so the no-model, keyless, offline path works out of
  the box; the exact value is a configuration/plan-phase detail.
- **The EPIC 4 default-provider setting is superseded**: Provider selection is driven entirely by the
  model prefix via the router, so the separate "default provider" setting from EPIC 4 is no longer
  consulted for routing; its removal or retention is a plan-phase cleanup detail.
- **Anthropic maximum-output-tokens**: Anthropic requires an explicit max-output-tokens on every call;
  it comes from configuration with a sensible default. The exact setting name and default value are
  plan-phase details.
- **Official clients**: The OpenAI and Anthropic adapters use the providers' official client libraries
  and expose the same asynchronous port as the Ollama adapter; the concrete client wiring is a
  plan-phase detail.
- **Error-status mapping**: Unreachable/missing-model → 503; timeout → 504; rate limit (429 upstream) →
  429 (no retry); missing/invalid API key → 503 (naming the key); unrecognized model prefix → 400. All
  mappings live in one place. The unknown-model 400 is decided at routing time, before any provider call.
- **Deprecated/unknown model status**: When a model with a recognized prefix is rejected by the provider
  (deprecated/unknown to that provider), the adapter surfaces the provider's own error through the same
  centralized taxonomy; the precise status for that upstream rejection is a plan-phase detail consistent
  with the existing kinds (treated as an upstream provider failure).
- **Keys optional at startup**: As in EPIC 4's configuration, provider API keys are optional to start the
  process; a request that routes to a provider missing its key fails on first use with a 503 naming the
  key, not at startup.
- **Reachability check reserved**: The provider port's lightweight reachability check is implemented by
  every adapter (and the router) but, as in EPIC 4, its consumption by a per-provider `/health` endpoint
  is a later epic; this epic does not add that endpoint.
- **Trusted demo context**: As in EPIC 4, the chat endpoint runs in a trusted/development context for the
  thesis demonstration; authentication and hardened exposure are out of scope, but the no-PII-in-logs and
  no-PII-to-provider rules (FR-024) still hold without exception (Constitution I, VIII).
- **Polish civil-law contracts** remain the target use case; the EPIC 3/EPIC 4 reversibility, AES-256
  mapping, TTL, and no-PII-in-logs guarantees are unchanged and must hold for every provider.
