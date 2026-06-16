# Implementation Plan: EPIC 3 — Realistic Fake-Data Generator and Reversible Session Mapping Store

**Branch**: `im/03-fake-data-generator` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-fake-data-generator/spec.md` (+ Clarifications session 2026-06-16)

## Summary

Add the **substitution + reversible-mapping** layer to the existing `gateway-api` backend, sitting
between Epic 2's `DetectionEngine` (reused, not reimplemented) and the Epic 4 LLM proxy (later). Given
Polish text and a session id, it (1) **generates** a realistic Polish synthetic replacement for each
detected entity, (2) **stores** the original↔fake mapping reversibly and securely, and (3) keeps the
mapping **consistent** across a multi-turn session, including across Polish grammatical inflection.

Three new internal packages keep pure logic separate from I/O, mirroring Epic 2's split:

- **`gateway_api/pseudonym_generation/`** — a stateless `FakeDataGenerator.generate(entity) -> FakeValue` built on
  **Faker(`pl_PL`)** (Constitution VII), with per-type builders that emit **checksum-valid** identifiers
  (PESEL with preserved gender + post-2000 offset; NIP/REGON/bank via mod-97 and REGON variant kept),
  valid Polish phones, realistic e-mails/cities/addresses, and dates shifted within **±10 years**. Plus
  **`inflection.py`** — a pure suffix-substitution declension engine (NO new NLP dependency) covering the
  common Polish patterns, with a documented base-form fallback (Constitution IX).
- **`gateway_api/pseudonym_vault/`** — the **encrypted session store** over Epic 1's singleton async Redis. One
  Redis **HASH per session** (`session:{id}`), **AES-256-GCM** encryption of original PII at rest
  (Constitution III), per-type mapping keys, sliding TTL, atomic clear/list, and the coreference +
  fuzzy-restore matching logic.
- **`gateway_api/api/`** — two thin debug routes, **`POST /v1/pseudonymize`** and
  **`POST /v1/depseudonymize`**, that reuse `DetectionEngine` and the new modules to demonstrate the full
  round-trip (including inflection) with **no LLM** call.

Epic 2 is **extended, not frozen**: `DetectedEntity` gains optional `lemma` and `case`, populated for
PERSON/LOCATION from the spaCy token (lemma + `token.morph` `Case`). These two fields are what make
case-aware substitution tractable — we always *generate* fake forms from a known base + known pattern,
and we read the original's base + case from spaCy. Per the spec clarifications: **only original PII is
encrypted** (fakes are synthetic and serve as the plaintext reverse index; forward field names are a
**keyed HMAC** of the normalized original); the **default TTL is 30 minutes** (sliding); fake **dates are
uniformly ±10 years** (no birth-vs-non-birth classification); and an **ambiguous surname-only** reference
that matches two or more stored people becomes a **new person** (never a guess). Unlike Epic 2's
`/v1/detect`, these routes **require Redis** and so fall under Epic 1's Redis gate automatically.

## Technical Context

**Language/Version**: Python 3.12 (backend `apps/gateway-api`); no frontend work in this epic.

**Primary Dependencies**: FastAPI + uvicorn (existing); **`faker`** (new — `pl_PL` locale, mandated by
Constitution VII); **`cryptography`** (new — `AESGCM` for AES-256-GCM); reuses Epic 2's
`presidio-analyzer` + spaCy `pl_core_news_lg` (for detection and the new lemma/Case enrichment) and
Epic 1's `redis.asyncio`. Inflection and the bounded fuzzy match are **pure Python — no new NLP or
edit-distance dependency**. Package manager: `uv` via `@nxlv/python`. Tests: `pytest`; **`fakeredis`**
(new dev dep) for store integration tests with no real Redis.

**Storage**: Redis 7 (Epic 1 instance), one **HASH per session** keyed `session:{session_id}`, with a
single `EXPIRE` covering the whole session. Original PII is stored **AES-256-GCM encrypted** inside field
values only; field names are non-reversible (HMAC of the normalized original, or the synthetic fake form
which is safe in clear). No new datastore. Redis restart loses the session by design (FR-027).

**Testing**: `pytest` per `apps/gateway-api/tests/` (`nx run gateway-api:test` → `uv run pytest tests/`).
Generator, inflection, encryption, key-strategy and matching tests are **pure / model-free**; store tests
run against **`fakeredis`**; the API round-trip test patches the analyzer (Epic 2's `patch_analyzer`
fixture pattern) so it needs **no model**. A full end-to-end round-trip with the real model is exercised
via `quickstart.md`.

**Target Platform**: Linux container (Docker Compose) and native macOS/Linux dev (uvicorn). Same as
Epic 1/2.

**Project Type**: Web-service backend in an Nx integrated monorepo. Two self-contained Python packages
(`pseudonym_generation/` pure, `pseudonym_vault/` I/O) plus two thin FastAPI routes; Epic 2's `pii_detection/` extended in three
small places.

**Performance Goals**: No latency/throughput SLA in this epic (spec: out of scope). Operations are O(1)
Redis round-trips per entity (`HGET`/`HSET` on one hash, one `EXPIRE`); `get_all_mappings` is one
`HGETALL`; `delete_session` is one `DEL`. The Epic 1 `GET /health` < 500 ms budget is untouched (no
new health dependency).

**Constraints**: Polish only (Faker `pl_PL`, Polish inflection/identifiers). **AES-256** at rest — GCM,
fresh 96-bit nonce per encryption, key never logged or returned (Constitution III). **No PII in logs** —
session_id, entity types/counts, timings only; never originals or fake↔original pairs (Constitution
VIII). Synchronous request/response only (Constitution V). Deterministic, seed-injectable generators for
reproducible tests. Abstract placeholder tokens are forbidden (Constitution VII).

**Scale/Scope**: Thesis/demo scale, single host. ~10 fake builders, one inflection engine (6 cases ×
common patterns), one AES-256-GCM helper, one MappingStore (5 methods), two debug endpoints, and three
small Epic-2 extensions (DTO fields, engine enrichment, checksum generation helpers).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0. This is the epic that exercises the **substitution** and **reversibility**
principles directly (Epic 2 left them N/A).

| Principle | Applicability to Epic 3 | Status |
|-----------|-------------------------|--------|
| I. Privacy by Design | This layer *is* the pseudonymization step. No LLM is called this epic; the debug endpoints have no outbound traffic. The store never exposes original PII (encrypted at rest, key system-side only). | ✅ Pass |
| II. Recall over Precision | Detection is reused unchanged from Epic 2; Epic 3 substitutes whatever was detected (no new precision/recall tuning). | ✅ N/A |
| III. Reversibility within Session | **Central.** Bidirectional mapping; **AES-256-GCM** at rest; key from `REDIS_ENCRYPTION_KEY`, never exposed to provider/client/logs; Redis-only, system-side; per-session **sliding TTL** + explicit clear. | ✅ Pass |
| IV. Provider Agnosticism | No LLM provider touched; the debug endpoints prefigure Epic 4 but call nothing external. | ✅ N/A |
| V. Synchronous Only | `pseudonymize`/`depseudonymize` are synchronous request/response; restore happens only over fully-supplied text. | ✅ Pass |
| VI. Polish First | Faker `pl_PL`; Polish-specific inflection (PERSON/LOCATION) and identifiers (PESEL/NIP/REGON/NRB). No English path. | ✅ Pass |
| VII. Realistic Substitution | **Central.** Realistic `pl_PL` values; checksum-valid IDs; PESEL gender preserved; REGON variant preserved; valid Polish phone; **no `[PERSON_1]`-style tokens**. | ✅ Pass |
| VIII. No PII in Logs | Generator/store/endpoints log session_id, types, counts, timings only — never originals, fakes, or pairs. Enforced by design and a test. | ✅ Pass |
| IX. Simplicity over Completeness | Inflection is pragmatic (common patterns; rare/foreign → base form), address atomic, no name↔PESEL gender link, no cross-field DOB coherence, Redis-restart loses the session — **all documented limitations**. | ✅ Pass |

**Technology Constraints**: Python 3.12 + FastAPI ✅; **Faker `pl_PL`** ✅ (now actually used — mandated);
**Redis + AES-256** ✅ (GCM via `cryptography`); Presidio + spaCy `pl_core_news_lg` reused ✅; no provider
coupling ✅. New libraries (`faker`, `cryptography`, dev-only `fakeredis`) are **additive within the
mandated stack** — no deviations. `cryptography.AESGCM` is the AES-256 mechanism; **Fernet (AES-128) is
rejected** as it would violate "AES-256".

**Spec-clarified interpretation (not a deviation)**: Constitution III says mapping data is "AES-256
encrypted". Per spec clarification Q1, **synthetic fakes are not personal data**, so only original PII is
encrypted; fakes are stored in clear as the reverse index and forward field names are a keyed HMAC of the
normalized original. No real PII is ever readable without the key, so Privacy-by-Design intent holds.
Recorded explicitly here so the gate is unambiguous; this is an interpretation of "personal data", **not**
a `# CONSTITUTION EXCEPTION`.

**Gate result: PASS.** Complexity Tracking is empty. Three design points refine the user-supplied approach
for security/correctness — keyed HMAC field names (D4), pure-Python bounded fuzzy match (D8), and the
spaCy-artifact reuse for lemma/Case (D1) — each documented with rationale in [research.md](research.md);
none is a constitution deviation.

## Project Structure

### Documentation (this feature)

```text
specs/003-fake-data-generator/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature spec (+ Clarifications session 2026-06-16)
├── research.md          # Phase 0 — decisions: lemma/Case, inflection method, AES-256-GCM, key strategy, store layout, coreference, fuzzy restore, collisions
├── data-model.md        # Phase 1 — FakeValue, Session/meta, Mapping field layout, DetectedEntity delta, encryption envelope
├── quickstart.md        # Phase 1 — round-trip validation guide (native + container)
├── contracts/           # Phase 1
│   ├── pseudonymize.openapi.yaml  # POST /v1/pseudonymize + /v1/depseudonymize schemas, 503-when-Redis-down
│   ├── mapping-store.md           # MappingStore method contracts, key strategy, hash layout, TTL semantics
│   ├── generators.md              # per-type fake-builder contract (validity rules, gender, variant, ±10y, collision fallback)
│   ├── inflection.md              # classify/decline/all_forms; pattern bands × six cases; fallback (the "method")
│   └── encryption.md              # AES-256-GCM envelope, key source, what-is-encrypted, HMAC field names
├── checklists/
│   └── requirements.md  # spec quality checklist (16/16)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

New code is additive inside the existing `gateway-api` app; **bold** = new, *italic* = modified.

```text
apps/gateway-api/
├── pyproject.toml                          # *add faker, cryptography; dev-group: fakeredis*
├── README.md                               # *append Epic 3 known-limitations section (Constitution IX)*
├── gateway_api/
│   ├── main.py                             # *register pseudonymize router (NOT gate-exempt → Redis-gated automatically)*
│   ├── config.py                           # *redis_session_ttl default 3600 → 1800 (FR-009: 30 min); redis_encryption_key already validated to 32B*
│   ├── dependencies.py                     # (unchanged — reuse get_redis_client())
│   ├── pii_detection/                          # ── Epic 2 (extended in 3 small places) ──
│   │   ├── dto.py                          # *DetectedEntity: add lemma: str | None = None, case: str | None = None*
│   │   ├── nlp.py                          # *add get_doc(text) / morphology access over the spaCy pipeline (research D1)*
│   │   ├── engine.py                       # *enrich kept PERSON/LOCATION DTOs with lemma + morph Case (research D1)*
│   │   └── checksums.py                    # *add control-digit GENERATION helpers (pesel/nip/regon9/regon14/nrb), reusing existing weights*
│   ├── pseudonym_generation/                         # ── new: pure, stateless, seed-injectable ──
│   │   ├── __init__.py                     # exports FakeDataGenerator, FakeValue
│   │   ├── dto.py                          # **FakeValue (entity_type, base, forms: dict[str,str] | None, gender | None)**
│   │   ├── generator.py                    # **FakeDataGenerator.generate(entity) — dispatch on entity_type; Faker(pl_PL); injectable seed**
│   │   ├── builders/
│   │   │   ├── __init__.py
│   │   │   ├── person.py                   # **gendered first+last; post-filter surname to declinable patterns**
│   │   │   ├── identifiers.py              # **PESEL (gender+post-2000), NIP, REGON (variant kept), bank account (mod-97)**
│   │   │   ├── contact.py                  # **email; Polish phone (valid format)**
│   │   │   ├── location.py                 # **city; atomic address (street + postcode + city)**
│   │   │   └── date_pl.py                  # **DD.MM.YYYY; uniform ±10y shift (research D9)**
│   │   └── inflection.py                   # **classify(name,gender)->Pattern; decline(base,pattern,case); all_forms(); suffix tables (research D2)**
│   ├── pseudonym_vault/                            # ── new: encrypted session store (async Redis I/O) ──
│   │   ├── __init__.py                     # exports MappingStore, get_mapping_store
│   │   ├── encryption.py                   # **AESGCM (AES-256-GCM): encrypt/decrypt, nonce||ct||tag; key from settings (research D3)**
│   │   ├── keys.py                         # **per-type mapping key (lemma / normalized digits / normalized text) + HMAC field-name (research D4)**
│   │   ├── session.py                      # **SessionMeta dataclass; field-name prefixes (fwd:/rev:/forms:/meta)**
│   │   ├── matching.py                     # **bounded Levenshtein(≤2) + lemma-containment coreference (research D7/D8)**
│   │   └── store.py                        # **MappingStore: get_or_create / get_original / get_all_mappings / delete_session / extend_ttl (research D5/D6)**
│   └── api/
│       ├── __init__.py                     # (unchanged)
│       └── pseudonymize.py                 # **POST /v1/pseudonymize + /v1/depseudonymize (thin; reuse DetectionEngine + store)**
└── tests/
    ├── conftest.py                         # *add fixtures: seeded_faker, mapping_store (fakeredis), enc_key, patch_analyzer reuse*
    ├── test_pseudonymize_api.py            # **round-trip incl. case change; session create/return; Redis-down 503; empty input; no-PII logs**
    ├── pseudonym_generation/
    │   ├── __init__.py
    │   ├── test_person.py                  # **gender consistency; declinable-surname filter; determinism with seed**
    │   ├── test_identifiers.py             # **valid checksums; PESEL gender + post-2000; REGON 9/14 kept; mod-97**
    │   ├── test_contact.py                 # **Polish phone format; email shape**
    │   ├── test_location.py                # **city; atomic address**
    │   ├── test_date_pl.py                 # **±10y window; DD.MM.YYYY**
    │   ├── test_inflection.py              # **each pattern × 6 cases; indeclinable fallback; independent first/last; city**
    │   └── test_generator.py               # **dispatch by type; seed reproducibility**
    └── pseudonym_vault/
        ├── __init__.py
        ├── test_encryption.py              # **round-trip; unreadable w/o key; distinct nonces; AES-256 keylen**
        ├── test_keys.py                    # **separator-insensitive key; same-literal-two-types distinct; HMAC field names carry no PII**
        ├── test_matching.py                # **bounded edit distance ≤2; containment scoped to same type**
        └── test_store.py                   # **fakeredis: bidirectional; TTL refresh+expiry; delete; get_all; collision retry+fallback; coreference; same-root distinct; ambiguous→new**
```

**Structure Decision**: Two cohesive new packages — **`pseudonym_generation/`** (pure, stateless, deterministic
with an injectable seed; builders one-per-domain mirroring `pii_detection/recognizers/`) and **`pseudonym_vault/`**
(all Redis I/O and crypto) — plus two thin routes under `api/`. Pure logic is isolated from I/O exactly as
Epic 2 isolated `checksums.py` from the analyzer, so generators/inflection/encryption/keys unit-test with
no Redis and no model. Epic 2's `pii_detection/` is touched in only three additive spots (DTO fields, an
engine enrichment pass, checksum generation helpers). No shared `libs/` is introduced — consistent with
Epic 1/2; the layer is internal to `gateway-api` and exposed via `FakeDataGenerator`, `MappingStore`, and
the two endpoints.

## Implementation Phases

These phases drive the eventual `tasks.md` (`/speckit-tasks`). Each is independently verifiable; later
phases depend on earlier ones.

- **Phase 0 — Deps & Epic-2 extensions**: add `faker` + `cryptography` (runtime) and `fakeredis` (dev) to
  `pyproject.toml`, `uv lock`/`sync`; extend `DetectedEntity` with `lemma`/`case`; add control-digit
  **generation** helpers to `pii_detection/checksums.py` (reusing existing weight tuples); add spaCy
  morphology access to `pii_detection/nlp.py` and an enrichment pass in `pii_detection/engine.py` that fills
  `lemma` + `case` for kept PERSON/LOCATION (research D1). *Verify*: DTO carries the new fields; checksum
  generators produce values that pass the existing `*_is_valid`; on `"Jan Kowalski mieszka w Warszawie"`
  the engine fills lemma/Case for PERSON/LOCATION (skip-if-no-model guard).
- **Phase 1 — Encryption (model-free)**: `pseudonym_vault/encryption.py` — `AESGCM` with the 32-byte key from
  `REDIS_ENCRYPTION_KEY`, fresh 96-bit nonce, envelope `nonce||ciphertext||tag` (research D3). *Verify*:
  `test_encryption` — round-trip, distinct nonces across calls, ciphertext unreadable/garbage without the
  key, 32-byte key asserted (AES-256).
- **Phase 2 — Inflection (pure)**: `pseudonym_generation/inflection.py` — `classify(name, gender) -> Pattern`,
  `decline(base, pattern, case) -> str`, `all_forms(base, pattern) -> dict[case,str]` over fixed suffix
  tables for {nom, gen, dat, acc, instr, loc}; adjectival -ski/-ska, masculine consonant (fleeting-e,
  stem softening), feminine -a (k/g softening), city patterns, and INDECLINABLE fallback (research D2).
  *Verify*: `test_inflection` — each pattern across the six cases, indeclinable → base form,
  first-name/surname classified+declined independently, city patterns.
- **Phase 3 — Fake generators (pure, seeded)**: `pseudonym_generation/dto.py` (`FakeValue`), per-type builders
  (`person`, `identifiers`, `contact`, `location`, `date_pl`), and `generator.py` dispatch with an
  injectable Faker seed (research D9). Builders compute `all_forms` for PERSON/LOCATION via Phase 2.
  *Verify*: per-type tests — valid checksums, PESEL gender + post-2000, REGON variant kept, Polish phone
  & DD.MM.YYYY formats, ±10y date window, seed reproducibility, declinable-surname post-filter.
- **Phase 4 — Mapping store (Redis I/O)**: `keys.py` (per-type mapping key + HMAC field-name strategy —
  research D4), `session.py` (meta + field prefixes), `matching.py` (bounded Levenshtein ≤2 + same-type
  lemma containment — research D7/D8), `store.py` — `get_or_create` (exact-key hit → coreference resolve →
  generate; collision retry ×3 then per-type fallback — research D6), `get_original` (exact rev → bounded
  fuzzy), `get_all_mappings` (one `HGETALL` + decrypt), `delete_session` (one `DEL`), `extend_ttl`; **every
  successful op refreshes the sliding TTL** (research D5). *Verify*: `test_store` against `fakeredis` —
  bidirectional mapping, TTL refresh + expiry, delete, get_all, hash-per-session layout, collision
  fallback, full-name→surname-only reuse, same-root people distinct, ambiguous surname → new person.
- **Phase 5 — API wiring**: `api/pseudonymize.py` — `POST /v1/pseudonymize` (detect → `get_or_create` per
  entity → replace spans **end→start**; PERSON/LOCATION inserted in the original's case via
  `decline(fake_base, entity.case)`; generate+return a `session_id` if absent) and
  `POST /v1/depseudonymize` (load session → replace fake forms with originals **longest-first**,
  word-boundary aware; case-aware restore via `decline(orig_base, matched_case)`; exact then bounded-fuzzy
  lookup). Register both in `main.py` (**not** gate-exempt → Redis-gated automatically); set
  `redis_session_ttl` default to 1800 (FR-009). *Verify*: `test_pseudonymize_api` — round-trip restores
  the original including a different grammatical case; `session_id` created and echoed; empty input → empty
  result + session, no error; Redis-down → 503 (Epic 1 gate); logs carry no PII.
- **Phase 6 — Limitations doc**: record the Constitution-IX limitations (no name↔PESEL gender link; no
  cross-field DOB coherence; inflection limited to common patterns, rare/foreign → base form; address
  atomic / not inflected; Redis restart loses the session) in `apps/gateway-api/README.md` and link from
  `quickstart.md`.

## Key Technical Decisions

Full decision + rationale + alternatives in [research.md](research.md). Summary:

| Decision | Rationale |
|---|---|
| **Extend `DetectedEntity` with `lemma`/`case`; fill them in the engine by mapping kept PERSON/LOCATION spans back to spaCy tokens** (reuse the model's lemmatizer + morphologizer `Case`) | Case-aware substitution needs the original's base form and grammatical case; `pl_core_news_lg` already provides both — no new NLP dependency (Constitution VI/IX). Other types leave them `None`. (research D1) |
| **Pure suffix-substitution declension; we only ever GENERATE forms from a known base + pattern** | The hard direction (arbitrary surface → lemma+case) is delegated to spaCy; we only generate, which fixed suffix tables handle for the common patterns. Documented as a "method" for the thesis; rare/foreign → base form. Morfeusz/morphological generators rejected (heavy dep, out of scope). (research D2) |
| **AES-256-GCM via `cryptography`'s `AESGCM`; envelope `nonce‖ciphertext‖tag`, fresh 96-bit nonce per op; key = 32 bytes from `REDIS_ENCRYPTION_KEY`** | Authenticated AES-256 at rest (Constitution III). Fernet (AES-128-CBC) rejected — violates "AES-256". (research D3) |
| **Encrypt ORIGINAL PII only; fakes stored in clear as the reverse index; forward field name = HMAC-SHA256(key, normalized original)** | Spec clarification Q1 (fakes are not personal data). **HMAC (keyed)** chosen over plain SHA-256 because small-domain identifiers (PESEL/NIP) are trivially brute-forced from an unkeyed digest; the key never leaves the system, so HMAC keeps originals out of field names *and* resists offline dictionary attacks. (research D4) |
| **One Redis HASH per session (`session:{id}`) with `fwd:`/`rev:`/`forms:`/`meta` fields; one `EXPIRE`; sliding TTL refreshed on every successful op (default 1800s)** | Atomic lifecycle: `DEL` clears all mappings at once (FR-010), `HGETALL` lists all (FR-011), one TTL governs the whole session and is reset on activity (FR-009). Per-mapping keys rejected (no atomic clear/expire, more round-trips). (research D5) |
| **Collision handling in `MappingStore.get_or_create`: retry the stateless generator ×3, then a per-type deterministic fallback** (numeric suffix for IDs/email; **re-roll, never a suffix, for names**) | Generator stays stateless/pure (FR-015); the store owns session-uniqueness and guarantees a unique fake; an unrealistic suffix on a name would violate Constitution VII. (research D6) |
| **Coreference: exact forward-key hit first; for PERSON/LOCATION, match the new lemma against existing same-type originals by full-lemma containment before generating; ambiguous (≥2 matches) → new person** | Full-name→surname-only reuse (FR-013) without merging distinct same-root people (FR-014); never guesses among ambiguous matches (spec clarification Q2). Fragment/fuzzy coreference rejected (merges "Anna Kowalska" with "Jan Kowalski"). (research D7) |
| **Fuzzy restore via a pure-Python bounded Levenshtein (≤2), no new dependency** | Absorbs minor unforeseen inflection of a fake on the restore path; bounded cost; avoids a C-extension dep (`rapidfuzz`/`python-Levenshtein`) unjustified at this scale. (research D8) |
| **Uniform ±10-year shift for ALL `DATE_TIME`; output `DD.MM.YYYY`** | Spec clarification Q4 — no birth-vs-non-birth classification needed; any date stays plausible. (research D9) |
| **These routes require Redis → register them WITHOUT adding to `_GATE_EXEMPT_PATHS`** | Epic 1's middleware already 503s every non-exempt route when Redis is down; the substitution path genuinely depends on Redis (unlike Epic 2's stateless `/v1/detect`), so default gating is exactly correct — zero gate code changes. (research D5) |

## Complexity Tracking

> No constitution violations. Section intentionally empty.
