# Research: EPIC 8 (partial) — Gateway PII Evaluation Harness

**Feature**: `specs/008-gateway-eval-harness` | **Date**: 2026-06-25

This document resolves the design decisions for the black-box evaluation harness `apps/gateway-eval`. The
gateway under test is frozen (no logic change beyond the additive `echo/` route in D2); the harness is a
new, isolated Nx Python app. Each decision records what was chosen, why, and the alternative rejected.

---

## D1 — Ground-truth independence (anti-circularity)

**Decision**: Ground truth comes **only** from the corpus gold standard — for synthetic documents it is
produced **automatically** at injection time (exact offsets are known because the harness placed the PII);
for real documents it is **manually annotated** to the same schema. The harness MUST NOT use the
gateway's own `entities`/`entities_replaced`/session `mappings` as the reference for **any** metric.

**Rationale**: Using the gateway's output as ground truth would measure the gateway against itself —
precision/recall would be ~1.0 by construction and the leak audit would be meaningless. The whole point is
an **external** oracle. The gateway's responses are the *predictions under test*, never the answer key.

**Consequence in code**: `scoring/` imports nothing from `gateway_api`. The only gateway-api imports in the
whole harness are in `corpus/synthetic_corpus_builder.py` (`FakeDataGenerator`) and indirectly via
`pii_detection.checksums` — both used to **build** the corpus, not to score it.

**Alternatives rejected**: Bootstrapping gold from `/v1/detect` then hand-correcting — still anchored to
the gateway's recall ceiling (it can't propose a span it never detects), so missed-entity types would be
systematically absent from the gold. Rejected.

---

## D2 — Two-stage split, and the additive `echo/` route

**Decision**: Two stages selected by `--stage 1|2|both`.
- **Stage 1 (no LLM)** isolates pseudonymization correctness: `POST /v1/detect` (detection spans),
  `POST /v1/pseudonymize` (outbound text + replacement offsets for the leak audit), `POST
  /v1/depseudonymize` (round-trip). No provider, so it is fast, deterministic, and the authoritative
  source for detection/leak/restoration metrics.
- **Stage 2 (full flow)** validates the **integrated** pipeline through `POST /v1/chat/completions` routed
  to the deterministic **Echo** provider, and harvests the gateway's own per-stage `timing_ms`.

To make Echo reachable over HTTP on the live stack, add **one additive factory entry** to the gateway
router: `"echo/": lambda: EchoProvider()` in `get_llm_provider`. A request with `model: "echo/echo"` then
routes to the existing `EchoProvider` (which echoes the last user message — i.e. the *pseudonymized* last
turn — so the gateway de-pseudonymizes it back to the original on the way out).

**Rationale**: Stage 1 gives clean component-level numbers without LLM noise; Stage 2 proves the assembled
flow and yields the timing breakdown the thesis reports. The `echo/` route is the smallest possible
enablement, is exactly the extension point **Constitution IV** sanctions (a new provider via the adapter
pattern, no pipeline change), and leaves every existing prefix and behaviour untouched.

**Alternatives rejected**: (a) **In-process ASGI app** with the Echo dependency-override for Stage 2 — zero
gateway change, but Stage 2 would no longer exercise the literal running container (weakens the "live
gateway" guarantee). Kept as the **test-only** mechanism for CI (`test_end_to_end.py`), not for real runs.
(b) **Real Ollama** for Stage 2 — non-deterministic paraphrasing breaks round-trip assertions, slow on
macOS, contradicts the deterministic-stub goal. Rejected. *(User-confirmed, 2026-06-25.)*

---

## D3 — Span-matching policy (primary overlap + strict-exact control)

**Decision**: Two policies, both reported.
- **Primary** — a predicted span matches a gold span when they share the **same (normalized) entity type**
  **and** their character ranges **overlap** (`pred.start < gold.end and gold.start < pred.end`). This
  answers the security question that matters: *was the PII masked at all?*
- **Strict** — same type **and exact** `(start, end)`. Reported as a secondary control number
  (`--strict-spans` makes it the headline instead).

Greedy one-to-one assignment per type, ordered by descending overlap length, so one prediction cannot
satisfy two gold spans (and vice versa); leftover gold → FN, leftover predictions → FP.

**Rationale**: Overlap is the standard, defensible NER-evaluation convention when boundary jitter (e.g. a
recognizer grabbing a trailing honorific or dropping a diacritic) should not count as a miss — for a
masking system, a partial-boundary mask still removes the PII. The strict number quantifies how much
boundary drift exists. Reporting both pre-empts the "why overlap?" thesis-defence question.

**Alternatives rejected**: Token-level F1 (needs a tokenizer contract shared with the gateway → coupling);
containment-only (asymmetric, under-counts when the prediction is narrower than gold). Rejected.

---

## D4 — Leak definition and the normalization rule

**Decision**: A leak is **any** occurrence, in the gateway's outbound text, of **any** original PII surface
from the gold standard — and **inflected or partial forms count as a FULL leak** (original `Kowalski`
surfacing as `Kowalskiego` is a full leak, not a near-miss). The pass bar is **zero leaks**.

Matching rule (documented, with its limitation):
1. **Normalize** both the outbound text and each original value: NFC Unicode, lowercase, collapse
   whitespace. Diacritics are **kept** (Polish `ł`, `ó`, `ż` are meaningful) — a separate diacritic-folded
   pass is run as a *defence-in-depth* secondary check so an accent-stripped leak is still caught.
2. For short structured identifiers (PESEL/NIP/REGON/bank account/email/phone) — match the **normalized
   exact** string (digits-only for numeric IDs, so formatting differences don't hide a leak).
3. For free-text values (PERSON/LOCATION/ADDRESS/DATE_TIME) — match on a **stem prefix**: derive a base by
   stripping common Polish inflectional endings and require a normalized substring match on a stem of
   length ≥ 4, **bounded by word boundaries** so a stem is not matched inside an unrelated longer word.
   Each gold value of length < 4 falls back to exact-token match to avoid spurious hits.

Every leak is recorded with `doc_id`, entity `type`, the original value, the **form found**, and its
offset in the outbound text.

**Rationale**: A pseudonymization system that leaves `Kowalskiego` has leaked the identity — inflection is
not an excuse. The stem rule catches Polish case inflection without a full morphological analyzer
(Constitution IX: documented simplification). The word-boundary bound and the length-4 floor keep the
false-leak rate near zero on common-word coincidences.

**Limitation (documented)**: heavy stem changes (e.g. `Paweł` → `Pawła`, dropped `e`) or suppletive forms
can be missed by a prefix rule; these are listed in the thesis limitations and are why the diacritic-folded
and exact-ID passes exist as backstops.

**Alternatives rejected**: Exact-string-only (misses every inflected leak — unacceptable for a security
audit). Full morphological lemmatization of the outbound text (heavy dependency, and the gateway's *own*
inflection handling is what we're testing — using the same tool would mask its gaps). Rejected.

---

## D5 — Latency sources (Stage 1 wall-clock vs Stage 2 `timing_ms`)

**Decision**: Two distinct latency channels, never mixed:
- **Stage 1** — the harness measures **wall-clock per endpoint** (`detect`, `pseudonymize`,
  `depseudonymize`) around each HTTP call (client-side `perf_counter`), so it includes network/serialization
  overhead and reflects what a caller experiences.
- **Stage 2** — the harness reads the gateway's **self-reported** `anonymization_meta.timing_ms`
  (`ner_analysis`, `fake_generation`, `redis_write`, `llm_request`, `deanonymization`, `total`), giving the
  per-stage internal breakdown the wall-clock can't see.

Both are **bucketed** by document length (character count) and by gold entity count, so the thesis can show
scaling.

**Rationale**: The two answer different questions (end-to-end caller cost vs internal stage cost). With the
Echo provider, `llm_request` is near-zero, which cleanly isolates the anonymization overhead — exactly the
quantity the thesis cares about.

**Alternatives rejected**: Relying on `timing_ms` for Stage 1 too — the Stage 1 endpoints don't return it,
and wall-clock is the honest figure for a per-endpoint caller. Rejected.

---

## D6 — RODO / data-handling regime for the real 40%

**Decision**: The entire evaluation runs **offline** against the local stack with the **Echo** provider, so
no contract text — synthetic or real — leaves the machine. Specifically:
- **Real contracts + any gold containing real originals** live under
  `gateway_eval/corpus/data/real/` and are **git-ignored** (added to root `.gitignore`); they are never
  committed and never sent to any external sink.
- The gateway's Redis (which holds encrypted original↔fake mappings during a run) is the **ephemeral,
  AES-256-encrypted** EPIC 3 store; the harness `DELETE`s each session after use and relies on TTL expiry.
- **Per-document results that embed originals** (e.g. the leak/restoration detail) are written to a results
  area treated as sensitive for the real subset; only **aggregate metrics** and **redacted/pseudonymized
  examples** are promoted into `thesis/images/` for publication.
- `error_analysis.py` emits, for `source="real"` documents, a **redacted/pseudonymized** variant safe to
  paste into the thesis (originals replaced by their type label or a synthetic stand-in).

**Rationale**: Polish civil-law contracts contain real personal data; RODO/GDPR requires data minimization
and no unnecessary disclosure. Offline + Echo + git-ignore + redaction satisfies this while still producing
publishable aggregate evidence.

**Alternatives rejected**: Committing the real corpus "for reproducibility" — unacceptable disclosure of
real PII. Anonymizing the real corpus before evaluation — would destroy the very ground truth the harness
needs. Rejected.

---

## D7 — Reproducibility (seeded Faker, versioned synthetic corpus, pinned templates)

**Decision**: The synthetic corpus is fully reproducible: `synthetic_corpus_builder.py` drives a
**seeded** `FakeDataGenerator(seed=…)` and a seeded `random.Random(seed)` for template/slot selection, so
the same `--seed` yields byte-identical documents and gold standard. The synthetic gold JSONL is
**committed** (versioned with the spec) and the contract **templates are pinned** in `corpus/templates/`.
Every run records its config (seed, base URL, gateway health snapshot, corpus version/hash, span policy,
timestamp) in the result envelope (D8 of data-model).

**Rationale**: A thesis result must be reproducible by a reviewer; seeding + versioning + a recorded config
make any reported number traceable to an exact corpus and gateway state.

**Alternatives rejected**: Regenerating the synthetic corpus on every run without committing it — numbers
would silently drift if generation logic changes. Rejected; the committed gold is the source of truth and
regeneration is a checked, opt-in `build-corpus` step.

---

## D8 — Entity-vocabulary normalization (gateway labels → gold vocabulary)

**Decision**: A single versioned alias map in `corpus/entity_vocabulary.py` maps the gateway's emitted
labels onto the **canonical gold vocabulary** (PERSON, LOCATION, ADDRESS, PESEL, NIP, REGON, BANK_ACCOUNT,
EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME). Confirmed gateway labels and their canonical targets:

| Gateway label(s) | Canonical gold type |
|------------------|---------------------|
| `PERSON` | PERSON |
| `LOCATION` | LOCATION |
| `POLISH_ADDRESS` | ADDRESS |
| `PESEL` | PESEL |
| `NIP` | NIP |
| `REGON` | REGON |
| `POLISH_BANK_ACCOUNT`, `NRB`, `IBAN` | BANK_ACCOUNT |
| `EMAIL_ADDRESS` | EMAIL_ADDRESS |
| `PHONE_NUMBER` | PHONE_NUMBER |
| `DATE_TIME` | DATE_TIME |
| `ORGANIZATION` (no gold counterpart) | → reported as **unmapped** **and** counted as a false positive |

Any label not in the map is **surfaced explicitly** in the report (never silently dropped or miscounted).

**Unmapped-label accounting (resolves analysis M2)**: an unmapped predicted span is recorded in
`DetectionReport.unmapped_labels` (its own visibility) **and** counted as a **false positive** in the
`SPURIOUS` column of the confusion matrix, so it lowers precision rather than vanishing. This keeps
precision **conservative** (an unrecognized recognizer output is treated as a spurious detection) and is
the single, documented rule both `entity_vocabulary.normalize_label()` (returns `None`) and
`detection_metrics` honour.

**Rationale**: The gold vocabulary and the gateway's recognizer labels differ (`POLISH_ADDRESS` vs
`ADDRESS`, three bank-account labels vs `BANK_ACCOUNT`). Without a documented map the confusion matrix would
be garbage. Surfacing unmapped labels turns "the gateway has no recognizer for X" into a **legitimate
finding** rather than a harness bug.

**Alternatives rejected**: Hard-coding the map inline in `detection_metrics.py` — hidden and untestable.
Auto-deriving aliases from string similarity — fragile. Rejected.

---

## D9 — CLI framework and orchestration

**Decision**: `typer` for the CLI, exposed via `gateway_eval/__main__.py` and an Nx `evaluate` target.
Flags: `--base-url` (default `http://localhost:8000`), `--corpus` (path; default committed synthetic +
git-ignored real if present), `--out` (default `thesis/images/`), `--stage {1,2,both}` (default `both`),
`--provider` (default `echo`), `--seed` (int, for `build-corpus`), `--strict-spans` (make exact-span the
headline). A separate `build-corpus` target (re)generates the synthetic corpus deterministically. The
orchestrator `run_evaluation.py`: health-gate → load/validate corpus → run selected stage(s) per document
(fresh session, `DELETE` after) → score → write results/figures/tables/error-analysis.

**Rationale**: `typer` gives typed enum flags (`--stage`) and clean help with little code; the eval app is
already dependency-isolated so the extra dependency has no production cost. The `evaluate`/`build-corpus`
split keeps the (slow, gateway-dependent) measurement separate from the (offline, seeded) corpus build.

**Alternatives rejected**: `argparse` (stdlib, but more boilerplate for enums/subcommands); a Jupyter
notebook (not reproducible/CI-able). Rejected.

---

## Resolved unknowns

All Technical-Context unknowns are resolved: language/deps (fixed above + D9), Echo routing (D2),
span policy (D3), leak rule (D4), latency channels (D5), data handling (D6), reproducibility (D7),
entity-label mapping (D8). No open `NEEDS CLARIFICATION` remains.
