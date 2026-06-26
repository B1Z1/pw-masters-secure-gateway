# Feature Specification: Gateway PII Evaluation Harness (EPIC 8, partial)

**Feature Branch**: `008-gateway-eval-harness`

**Created**: 2026-06-25

**Status**: Draft

**Input**: User description: "EPIC 8 (partial) — Evaluation harness: measure how well the LIVE gateway pseudonymizes and restores PII on a corpus of Polish civil-law contracts. Realises F-32, F-33, F-35, F-36. F-34 (LLM answer-quality A/B with ROUGE/BERTScore) is explicitly OUT of scope (future work). Build apps/gateway-eval: a BLACK-BOX evaluation harness that drives the live gateway HTTP API … against an INDEPENDENT gold standard … two stages (no-LLM correctness + full-flow with Echo provider), a hybrid 60/40 synthetic/real Polish-contract corpus, detection P/R/F1 + confusion matrix, an inflection-aware PII-leak audit (zero-leak bar), round-trip restoration fidelity, latency, and thesis-ready outputs."

## Overview

This feature delivers an **evaluation harness** — a separate research tool (`apps/gateway-eval`) that
measures how well the **live, unmodified** anonymization gateway detects, replaces, and restores
personally identifiable information (PII) on a corpus of Polish civil-law contracts. It is a **black-box**
evaluator: it drives the gateway only through its public HTTP endpoints (the same service a user runs
via `docker compose up`, default `http://localhost:8000`) and changes **no** gateway behaviour.

The deliverable is the **evidence base for the thesis evaluation chapter** (`thesis/content/06-testy-ewaluacja`):
detection-quality tables, a PII-leak proof, round-trip restoration figures, latency distributions, and a
concrete error analysis of edge cases and improvement opportunities.

**Critical methodological rule (anti-circularity)**: ground truth comes **only** from the corpus gold
standard. The harness MUST NEVER treat the gateway's own output (its detected/replaced entities or its
session mappings) as ground truth — doing so would make the evaluation circular and worthless.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stage 1: pseudonymization-correctness evaluation, no LLM (Priority: P1)

As the researcher, I run the no-LLM correctness stage over the whole corpus and obtain, per entity type
and in aggregate, how well the gateway **detects** PII, whether the outbound text is **leak-free**, and
whether originals are **correctly restored** — all scored against the independent gold standard, never
against the gateway's own answer.

**Why this priority**: This is the core thesis result and the minimum viable product. Without it there is
no measurement of pseudonymization quality. It depends on no LLM and is the cheapest, most deterministic
slice to run and re-run.

**Independent Test**: With the gateway healthy and any gold-standard corpus loaded (even a handful of
documents), run Stage 1 and confirm it produces per-type and aggregate Precision/Recall/F1, a confusion
matrix, a leak count, and a round-trip restoration breakdown, written as machine-readable results.

**Acceptance Scenarios**:

1. **Given** a healthy gateway and a gold-standard corpus, **When** the researcher runs Stage 1, **Then**
   the harness calls the detection, pseudonymization, and de-pseudonymization endpoints once per document
   and emits per-document and aggregate detection metrics (P/R/F1 per entity type, plus micro and macro
   aggregates) and a confusion matrix.
2. **Given** the gateway returns its detected/replaced entities, **When** the harness scores detection,
   **Then** it aligns those spans to the **gold** spans and uses **only the gold** entities as ground
   truth — never the gateway's entity list as the reference set.
3. **Given** detection scoring, **When** spans are aligned, **Then** the harness reports a **primary**
   metric (same entity type + character-span overlap — "was the PII masked") **and** a **strict** control
   metric (exact span boundaries) side by side.
4. **Given** the gateway emits its own label vocabulary (for example labels for Polish addresses, bank
   accounts, organizations), **When** the harness aligns to gold, **Then** it normalizes gateway labels to
   the canonical gold entity vocabulary through a documented, versioned alias map and reports any
   gateway label it could not map.
5. **Given** restoration results, **When** the harness scores round-trip, **Then** each original PII
   surface is classified by **how** it was recovered (exact / correct inflection / fuzzy-recovered /
   base-form-only / missed) and a document-level exact-restoration rate is reported.

---

### User Story 2 - Inflection-aware PII-leak audit, zero-leak bar (Priority: P1)

As the researcher, for every document I prove that **no original PII value** survives in the text the
gateway would send onward — counting inflected and partial forms (for example original `Kowalski`
surfacing as `Kowalskiego`) as a **full leak** — so the thesis can state, with evidence, that the
privacy guarantee holds (or report exactly where it does not).

**Why this priority**: This is the security-critical test of the project's privacy principles (Constitution
I and VIII). A leaked original PII value is the worst possible outcome, so this audit is the hard pass/fail
gate and is reported as its own headline result. It runs as part of Stage 1 but is called out separately
because of its inflection-aware matching and zero-leak bar.

**Independent Test**: Feed documents whose gold PII includes Polish surnames and place names that the
gateway is likely to leave in inflected form, run the leak audit, and confirm that any reappearance of an
original value — exact, inflected, or partial — is reported as a leak with its document, value, type, and
offset.

**Acceptance Scenarios**:

1. **Given** a document's pseudonymized outbound text, **When** the harness audits it, **Then** it scans
   for **any** occurrence of **any** original PII value drawn from the gold standard and flags every
   occurrence as a leak.
2. **Given** an original surname `Kowalski` that appears in the outbound text only as `Kowalskiego`,
   **When** the audit runs, **Then** that inflected form is counted as a **full leak**, not a partial or
   near-miss.
3. **Given** the full corpus, **When** the audit completes, **Then** the harness reports a total leak
   count, the per-document and per-type breakdown, and a clear pass/fail against the **zero-leak** bar.

---

### User Story 3 - Reproducible corpus build and privacy-safe real-contract ingestion (Priority: P2)

As the researcher, I build the evaluation corpus reproducibly and keep all real personal data on my
machine. The synthetic portion is generated from public Polish contract templates with realistic PII
injected at **programmatically known offsets** (so the gold standard is exact and automatic), and the real
portion is ingested and **manually annotated** to the same schema, with the real PII never leaving the
machine and never reaching the thesis.

**Why this priority**: The corpus is the foundation of every metric, but the eval logic (P1) can be
exercised against a small sample, so the full reproducible corpus is P2. Privacy of the real 40% is a hard
constraint.

**Independent Test**: With a fixed seed, build the synthetic corpus twice and confirm the documents and
gold standard are identical both times; ingest and annotate a sample real contract and confirm it conforms
to the shared gold-standard schema and that its files are excluded from version control.

**Acceptance Scenarios**:

1. **Given** a fixed seed, **When** the synthetic corpus is built, **Then** it is reproducible
   byte-for-byte (documents and gold standard) and uses valid Polish formats (PESEL / NIP / REGON / bank
   account with correct checksums, gender-consistent names, plausible addresses, emails, phones).
2. **Given** synthetic generation injects PII into templates, **When** a document is produced, **Then**
   every injected PII instance is recorded in the gold standard with its exact character offsets and type,
   with no manual annotation needed.
3. **Given** a real downloaded Polish contract, **When** it is ingested and manually annotated, **Then**
   it conforms to the same gold-standard schema (`doc_id`, `source`, `contract_type`, `text`, `entities`)
   and is marked as the `real` source.
4. **Given** the assembled corpus, **When** it is inspected, **Then** it contains at least 50 documents and
   at least 500 PII instances, all required entity types are represented, and the synthetic/real split is
   approximately 60/40.
5. **Given** real contracts and their gold standard contain originals, **When** the repository is examined,
   **Then** those files are excluded from version control and from any external sink, and only the
   synthetic gold standard is versioned.

---

### User Story 4 - Stage 2: full-flow evaluation with the Echo provider and per-stage timing (Priority: P2)

As the researcher, I run the **integrated** chat pipeline end to end against the deterministic Echo/stub
provider to confirm the whole flow behaves correctly — the content that reaches the provider is leak-free
and the de-pseudonymized answer restores correctly — and to collect the gateway's own per-stage timing
breakdown.

**Why this priority**: Stage 1 already proves correctness at the component endpoints; Stage 2 validates the
assembled pipeline and yields the per-stage timing the thesis reports. It is valuable but secondary to the
Stage 1 measurements and depends on the chat endpoint and provider routing being available.

**Independent Test**: With the gateway configured to route to the Echo provider, send each document through
the chat endpoint, confirm the declared outbound (pseudonymized) content is leak-free against gold, confirm
the returned answer restores the original PII, and confirm a per-stage timing breakdown is captured for
every document.

**Acceptance Scenarios**:

1. **Given** the Echo provider is the routed provider, **When** the harness sends a document through the
   chat endpoint, **Then** the call completes offline with no external network egress and returns a
   per-stage timing breakdown.
2. **Given** the chat response, **When** the harness audits the gateway's declared outbound (pseudonymized)
   content, **Then** that content is leak-free against the gold originals (same inflection-aware rule as
   User Story 2).
3. **Given** the Echo provider echoes the pseudonymized content, **When** the gateway de-pseudonymizes the
   answer, **Then** the restored answer contains the original PII values and the round trip is scored
   against gold.
4. **Given** Stage 2 runs, **When** results are aggregated, **Then** the gateway-reported per-stage timing
   (detection, fake generation, mapping write, provider call, restoration, total) is collected per
   document.

---

### User Story 5 - Thesis-ready outputs and error analysis (Priority: P2)

As the researcher, I get publication-ready artifacts — tables, figures, and a written error analysis — so I
can drop the evidence straight into the thesis evaluation chapter, including a concrete list of false
negatives, false positives, and restoration failures that becomes the "edge cases and what to improve"
section.

**Why this priority**: The measurements are only useful to the thesis once turned into figures, tables, and
an error narrative. This consumes the outputs of P1 and P2 stages and so follows them.

**Independent Test**: After a run, confirm machine-readable per-document and aggregate results exist (in
both a structured object format and a tabular format), that the expected figure set is rendered into the
configured output directory, and that an error-analysis report lists concrete failing cases.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** outputs are written, **Then** the harness produces both
   per-document and aggregate machine-readable results in a structured format and a tabular format.
2. **Given** the configured output directory (default `thesis/images/`), **When** figures are rendered,
   **Then** the harness produces at least a confusion-matrix heatmap, per-type Precision/Recall/F1 bars,
   latency distributions, and a restoration-outcome breakdown.
3. **Given** failing cases exist, **When** the error-analysis report is generated, **Then** it lists the
   concrete false negatives, false positives, and restoration failures with enough context (document,
   entity type, gold value vs. gateway behaviour) to drive improvement, while keeping real PII out of any
   published artifact (only aggregate metrics and redacted/pseudonymized examples appear).

---

### Edge Cases

- **Gateway unhealthy / degraded**: the health endpoint reports `degraded` (Redis down or detection model
  not loaded). The harness MUST fail gracefully — report the degraded state clearly and not crash or
  produce misleading metrics.
- **Detection endpoint not ready**: the detection or chat endpoint returns a "model not ready" error. The
  harness records the condition for the affected document rather than scoring it as a detection result.
- **Gateway emits an unmapped entity label**: a returned label has no entry in the gold alias map. The
  harness reports it explicitly instead of silently dropping or miscounting it.
- **Overlapping or adjacent gold spans**: two gold entities touch or overlap; the span-alignment policy
  must resolve this deterministically under both the overlap and strict matching variants.
- **A PII value appears multiple times in one document**: each occurrence is tracked independently for
  detection, leak audit, and restoration.
- **An original PII value is a substring of an unrelated common word**: the leak audit must define how it
  treats such coincidental matches so it neither over- nor under-counts leaks.
- **Restoration position drift**: the restored text restores the value but at a shifted offset (length
  change from inflection); the round-trip classifier must categorize this rather than discard it.
- **Real contract with messy text** (OCR artifacts, inconsistent whitespace, line breaks inside entities):
  ingestion and annotation must still produce valid offset-accurate gold entries.
- **Empty or whitespace-only document**: handled without error and excluded from rate denominators where
  appropriate.

## Requirements *(mandatory)*

### Functional Requirements

#### Scope, methodology, and safety

- **FR-001**: The harness MUST be a separate research tool (`apps/gateway-eval`), MUST NOT be part of the
  production gateway, and MUST exercise the gateway **only** through its public HTTP endpoints, changing no
  gateway behaviour.
- **FR-002**: The harness MUST use the corpus **gold standard as the sole source of ground truth** and MUST
  NEVER use the gateway's own detected/replaced entities or session mappings as the reference for scoring
  detection, leaks, or restoration.
- **FR-003**: The entire evaluation MUST run **offline** against the local stack using the deterministic
  Echo/stub provider, with **no contract text leaving the machine** — especially the real 40%.
- **FR-004**: The harness MUST treat **authentication as not required** (prototype) and MUST connect to a
  configurable gateway base URL (default `http://localhost:8000`).
- **FR-005**: Before evaluating, the harness MUST check gateway health and, if the gateway reports
  `degraded` (or is unreachable), MUST **fail gracefully** with a clear report rather than producing
  metrics.
- **FR-006**: F-34 (LLM answer-quality A/B comparison with ROUGE/BERTScore) is **explicitly out of scope**;
  the harness measures pseudonymization and restoration, not downstream answer quality.

#### Corpus and gold standard

- **FR-007**: The corpus MUST be **hybrid**: approximately 60% synthetic and 40% real Polish civil-law
  contracts, with **all required entity types represented**. The **synthetic portion alone** MUST
  independently satisfy the floor of **at least 50 documents** and **at least 500 PII instances**, so the
  evaluation is runnable and reproducible (including in CI) without the real set. The ~60/40 hybrid is the
  thesis-corpus composition, reached by adding the manually-annotated real portion on top of the synthetic
  baseline.
- **FR-008**: Both sources MUST share a **single gold-standard schema**: per document `{doc_id, source,
  contract_type, text, entities:[{type, start, end, text}]}` where offsets are character offsets into
  `text`.
- **FR-009**: The canonical gold entity vocabulary MUST cover: PERSON, LOCATION, ADDRESS, PESEL, NIP,
  REGON, BANK_ACCOUNT, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME.
- **FR-010**: The **synthetic** portion MUST be generated from public Polish contract templates
  (e.g. najem, zlecenie, o dzieło, sprzedaż) by injecting realistic PII at **programmatically known
  character offsets**, so the gold standard is produced **automatically and exactly** with no manual
  annotation.
- **FR-011**: Injected synthetic PII MUST use **valid Polish formats**: PESEL/NIP/REGON/bank-account
  numbers with correct checksums, gender-consistent names, plausible addresses, emails, and phone numbers.
- **FR-012**: Synthetic corpus generation MUST be **seeded and reproducible** — the same seed yields the
  same documents and the same gold standard.
- **FR-013**: The **real** portion MUST support an ingestion path plus **manual annotation** to the same
  gold-standard schema, with each document marked `source = real`.
- **FR-014**: Real-contract source files and any gold standard containing real originals MUST be **kept out
  of version control** and out of any external sink; only the synthetic gold standard is versioned. The
  versioned gold standard MUST be tracked so results are tied to a known corpus state.

#### Stage 1 — pseudonymization correctness (no LLM)

- **FR-015**: For each document, Stage 1 MUST call the **detection** endpoint, the **pseudonymization**
  endpoint, and the **de-pseudonymization** endpoint, and MUST measure **wall-clock latency per endpoint**.
- **FR-016**: Stage 1 MUST compute detection **Precision, Recall, and F1 per entity type**, plus **micro**
  and **macro** aggregates, and MUST produce a **confusion matrix** across entity types (including
  miss/spurious categories).
- **FR-017**: Detection scoring MUST use a **primary** span-matching policy of *same entity type + character
  span overlap* (reflecting "was the PII masked") and MUST report a **strict exact-span** variant alongside
  as a control number.
- **FR-018**: The harness MUST treat **recall as the priority metric** in its reporting (a missed PII is the
  worst outcome) while still reporting precision and F1.
- **FR-019**: The harness MUST **normalize gateway entity labels** to the canonical gold vocabulary via a
  documented, versioned alias map (for example mapping the gateway's Polish-address, bank-account, and
  organization labels onto the gold types), and MUST report any gateway label it cannot map.
- **FR-020**: Stage 1 MUST perform a **PII-leak audit** on the gateway's pseudonymized **outbound text**:
  for every document it scans for **any** occurrence of **any** original PII value from the gold standard.
- **FR-021**: The leak audit MUST count **inflected and partial forms** of an original value as a **full
  leak** (e.g. original `Kowalski` appearing as `Kowalskiego`), and MUST apply a **zero-leak pass bar**.
- **FR-022**: Stage 1 MUST measure **round-trip restoration fidelity**: after de-pseudonymization, for each
  original PII surface it determines whether the original is restored at the correct position, classified as
  **exact / correct-inflection / fuzzy-recovered / base-form-only / missed**, and reports a
  **document-level exact-restoration rate**.

#### Stage 2 — full flow with the LLM hop (Echo provider)

- **FR-023**: For each document, Stage 2 MUST call the **chat-completions** endpoint with the deterministic
  Echo/stub provider, verifying the integrated pipeline end to end.
- **FR-024**: Stage 2 MUST verify that the gateway's declared **outbound (pseudonymized) content is
  leak-free** against the gold originals, using the same inflection-aware leak rule as FR-021.
- **FR-025**: Stage 2 MUST verify that the **de-pseudonymized answer restores correctly** — the original
  PII values reappear in the restored answer — scored against gold.
- **FR-026**: Stage 2 MUST collect the gateway's **per-stage timing breakdown** reported in the chat
  response (detection, fake generation, mapping write, provider call, restoration, total).

#### Latency / performance

- **FR-027**: The harness MUST report **Stage 1 wall-clock latency per endpoint** and **Stage 2 per-stage
  timing** from the gateway's reported breakdown.
- **FR-028**: Latency results MUST be **bucketed by document length and by entity count** so the thesis can
  show how performance scales.

#### Outputs and reporting

- **FR-029**: The harness MUST produce **machine-readable results** at both **per-document** and
  **aggregate** granularity, in a structured object format and a tabular format.
- **FR-030**: The harness MUST render **thesis-ready figures** into a **configurable output directory**
  (default `thesis/images/`), including at least: a confusion-matrix heatmap, per-type Precision/Recall/F1
  bars, latency distributions, and a restoration-outcome breakdown.
- **FR-031**: The harness MUST produce an **error-analysis report** listing the concrete false negatives,
  false positives, and restoration failures (with document, entity type, and gold-vs-gateway context) that
  form the "edge cases and what to improve" section.
- **FR-032**: All published artifacts MUST contain **only aggregate metrics and redacted/pseudonymized
  examples** — **no real PII** from the real-contract portion ever appears in any output destined for the
  thesis.
- **FR-033**: Every evaluation run MUST record its **configuration** (seed, gateway base URL, gateway health
  snapshot, corpus version, span-matching policy, timestamp) so results are reproducible and traceable.

### Key Entities

- **Gold-standard document**: one corpus item — `doc_id`, `source` (`synthetic` | `real`), `contract_type`,
  full `text`, and a list of gold entities. The independent ground truth.
- **Gold entity**: a single known PII instance — `type` (canonical vocabulary), `start`/`end` character
  offsets into the document text, and the original `text` surface.
- **Corpus**: the assembled collection of gold-standard documents, partitioned into synthetic (versioned)
  and real (local-only) sources, satisfying the size, instance-count, type-coverage, and split targets.
- **Entity-label alias map**: the versioned mapping from gateway-emitted labels to the canonical gold
  vocabulary, plus the set of unmapped labels encountered.
- **Detection alignment**: per document, the matching between gateway-reported spans and gold spans under
  both the primary (overlap) and strict (exact) policies, yielding true positives, false positives, and
  false negatives per type.
- **Leak finding**: a single detected leak — `doc_id`, entity `type`, the original value, the form found
  (exact / inflected / partial), and its offset in the outbound text.
- **Restoration outcome**: per original PII surface, its recovery category (exact / correct-inflection /
  fuzzy-recovered / base-form-only / missed) and position correctness.
- **Latency sample**: a timing measurement tagged by stage/endpoint, document-length bucket, and
  entity-count bucket.
- **Evaluation run**: a single execution with its configuration, seed, gateway health snapshot, corpus
  version, and the per-document and aggregate results it produced.
- **Error-analysis entry**: one concrete failing case (false negative, false positive, or restoration
  failure) with the context needed to act on it, redacted of real PII.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The **committed synthetic corpus alone** contains **≥ 50 documents** and **≥ 500 PII
  instances** with **all 10 canonical entity types represented** (targets met without the real set, so CI
  and reproducibility runs pass standalone); the full thesis corpus adds the manually-annotated real portion
  to reach an approximately **60/40 synthetic/real** split.
- **SC-002**: A researcher can run the **full Stage 1 evaluation over the entire corpus with a single
  documented command** and obtain per-type and aggregate (micro + macro) Precision/Recall/F1, a confusion
  matrix, the leak count, and the round-trip restoration breakdown.
- **SC-003**: Detection quality is reported under **both** the primary (type + overlap) and strict
  (exact-span) policies, with **recall surfaced as the headline metric** per entity type and in aggregate.
- **SC-004**: The **PII-leak audit** reports an exact leak count against the **zero-leak pass bar**, and any
  leak — including an inflected or partial form of an original value — is captured with its document, value,
  type, and offset.
- **SC-005**: Round-trip restoration reports a **document-level exact-restoration rate** and a per-entity
  recovery breakdown across the five recovery categories.
- **SC-006**: Re-running the synthetic corpus build with the **same seed produces an identical corpus and
  gold standard**, and re-running an evaluation against an unchanged gateway and corpus reproduces the same
  metrics.
- **SC-007**: An evaluation run completes with **zero external network egress** (verifiably offline via the
  Echo provider), and **no real PII** appears in any artifact written for the thesis.
- **SC-008**: After a run, the configured output directory (default `thesis/images/`) contains the expected
  machine-readable results (per-document and aggregate) and **at least the four required figure types**, and
  an **error-analysis report** lists concrete false negatives, false positives, and restoration failures.
- **SC-009**: When the gateway is **unhealthy/degraded**, the harness reports the condition clearly and
  exits without crashing or emitting misleading metrics.
- **SC-010**: Stage 2 confirms, for every document, that the gateway's declared outbound content is
  **leak-free** and that the de-pseudonymized answer **restores the originals**, and it captures the
  gateway-reported per-stage timing.

## Assumptions

- **Gateway endpoints**: the harness targets the existing public surface — a detection endpoint
  (`POST /v1/detect`), pseudonymize / de-pseudonymize endpoints (`POST /v1/pseudonymize`,
  `POST /v1/depseudonymize`), the chat endpoint (`POST /v1/chat/completions`) whose response carries the
  per-stage timing breakdown, and the health endpoint (`GET /health`). These are assumed stable and
  unchanged by this feature.
- **Echo provider availability**: the gateway can be configured/routed so that chat requests resolve to the
  deterministic Echo/stub provider, which echoes the pseudonymized content back, enabling an offline
  end-to-end round trip.
- **Gateway label vocabulary**: the gateway emits labels such as `POLISH_ADDRESS`, `POLISH_BANK_ACCOUNT`,
  `NRB`/`IBAN`, `ORGANIZATION`, `LOCATION`, `DATE_TIME`, etc.; the alias map (FR-019) reconciles these to
  the canonical gold vocabulary (e.g. address-like → ADDRESS, bank-account-like → BANK_ACCOUNT). Where the
  gateway has no recognizer for a gold type, the resulting misses are a legitimate evaluation finding, not a
  harness defect.
- **Real-corpus provenance**: real Polish contracts are obtained and stored by the researcher locally; the
  harness assumes they are present in a local, git-ignored location and already (or to be) manually
  annotated to the gold schema. Sourcing the real contracts is the researcher's responsibility.
- **Inflection rule**: for the leak audit, "partial form" means a form sharing the original's stem/base
  (such as a Polish case-inflected variant); coincidental substring matches inside unrelated common words
  are handled by a documented matching rule so they are not miscounted.
- **Output directory default**: figures and reports default to `thesis/images/`, overridable by
  configuration; machine-readable results may live in a sibling results directory.
- **Run model**: the evaluation is a batch/offline run initiated by the researcher (no service, no
  scheduler); reproducibility comes from seeding plus a versioned synthetic gold standard.
- **One user message per document**: each corpus document is sent as a single `user` message, so the
  gateway's latest-turn outbound view (`input_anonymization.pseudonymized_content`) equals the whole
  document's outbound text — the Stage 2 leak audit on that field therefore covers the entire document.
- **Scale**: master's-thesis prototype scale (tens to low hundreds of documents); no concurrency or
  throughput SLA is required — latency is measured and reported, not enforced.
