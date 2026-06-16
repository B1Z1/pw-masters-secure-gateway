# Phase 0 Research — EPIC 3: Fake-Data Generator & Reversible Session Mapping Store

All decisions below resolve the "NEEDS CLARIFICATION" surface of the spec's Assumptions and the
user-supplied implementation guidance. Each is **Decision / Rationale / Alternatives considered**. The
mandated stack (Python 3.12 + FastAPI, Faker `pl_PL`, Redis + AES-256, Presidio + spaCy `pl_core_news_lg`)
is fixed by the constitution and not re-litigated here.

---

## D1 — Original base form + grammatical case via spaCy (extend `DetectedEntity`)

**Decision**: Add optional `lemma: str | None = None` and `case: str | None = None` to
`pii_detection/dto.py:DetectedEntity`. In `pii_detection/engine.py`, after overlap resolution and thresholding,
run an enrichment pass that, **for PERSON and LOCATION only**, maps each kept entity's `[start, end)` span
to the covering spaCy token(s) and fills `lemma` (the spaCy lemma; for multi-token persons, per-token
lemmas joined / classified independently downstream) and `case` (from `token.morph.get("Case")`, e.g.
`Nom`, `Gen`, `Dat`, `Acc`, `Ins`, `Loc`). All other entity types leave both `None`. The spaCy `Doc` is
obtained from the already-loaded NlpEngine (`pii_detection/nlp.py` gains a `get_doc(text)` / morphology
accessor) so there is **no second model and no new dependency**; `pl_core_news_lg` already ships a
lemmatizer and a morphologizer that emit the `Case` feature.

**Rationale**: Case-aware substitution is only tractable if we know, for the *original*, its base form and
its grammatical case — then we generate the matching case of the *fake*. spaCy already computes both for
Polish, so reusing it (Constitution VI — Polish First; IX — Simplicity) avoids a parallel morphology
stack. Confining enrichment to PERSON/LOCATION keeps the cost off the identifier/date/email/phone paths
that never inflect. Epic 2 explicitly left `DetectedEntity` un-frozen for this.

**Alternatives considered**:
- *A separate Morfeusz2 / morphological analyzer for lemma+case* — heavyweight extra dependency duplicating
  what spaCy already produces; rejected (Constitution IX).
- *Re-running a fresh `spacy.load()` pipeline in the engine* — a second model load and a second parse;
  rejected in favor of reusing the singleton NlpEngine's pipeline.
- *Carrying raw spaCy tokens on the DTO* — leaks Presidio/spaCy internals across the engine boundary;
  rejected (keep the DTO a stable project contract, per Epic 2 D7).

---

## D2 — Polish inflection as pure suffix-substitution tables ("generate-only")

**Decision**: `pseudonym_generation/inflection.py` is pure Python with three functions —
`classify(name, gender) -> Pattern`, `decline(base, pattern, case) -> str`,
`all_forms(base, pattern) -> dict[str, str]` — over fixed suffix-substitution tables for the six cases
{nom, gen, dat, acc, ins, loc}. Patterns: adjectival masculine (`-ski/-cki/-dzki`), adjectival feminine
(`-ska/-cka/-dzka`), masculine-noun consonant-ending (incl. fleeting-e `Marek→Marka` and common stem
softening), feminine `-a` (incl. k/g softening `Anka→Ance`), city patterns (masculine `-ów`/consonant,
feminine `-a`, neuter), and **INDECLINABLE** (foreign names, female surnames not ending `-a`, `-o`
endings). First name and surname are classified and declined **independently**. The crucial simplification:
we **only ever generate** forms from a *known base + known pattern* — never parse an arbitrary surface form
(that direction is spaCy's job via D1). The bands/rules are documented so the thesis can describe inflection
as a method.

**Rationale**: Full Polish morphology in both directions is hard; restricting to *generation from a
classified base* makes fixed tables sufficient for the common patterns the spec scopes (Constitution IX).
Independent first/last classification matches "Jana Kowalskiego" = gen(Jan)+gen(Kowalski). INDECLINABLE
fallback satisfies the documented-limitation requirement for rare/foreign names.

**Alternatives considered**:
- *Morfeusz2 generation* — full coverage but a heavy native dependency and out of scope for a prototype;
  rejected (Constitution IX; the user explicitly required "no new NLP dependency").
- *Inflect every detected surface independently with a learned model* — non-deterministic, untestable as a
  "method"; rejected.

---

## D3 — AES-256-GCM via `cryptography`'s `AESGCM`

**Decision**: `pseudonym_vault/encryption.py` uses
`cryptography.hazmat.primitives.ciphers.aead.AESGCM`. The key is the 32 raw bytes decoded from
`REDIS_ENCRYPTION_KEY` (already base64-validated to exactly 32 bytes in `config.py`). Each `encrypt`
generates a fresh **96-bit (12-byte) random nonce** and returns the envelope `nonce || ciphertext || tag`
(GCM tag appended by `AESGCM.encrypt`); `decrypt` splits the nonce and verifies the tag. Encrypt/decrypt
are transparent to callers (bytes in / bytes out; values are UTF-8/JSON before encryption).

**Rationale**: AES-256 with authentication (GCM detects tampering of the at-rest blob) directly satisfies
Constitution III. A 96-bit random nonce per message is the GCM-recommended size; storing it alongside the
ciphertext is standard. Reusing the already-validated 32-byte key means no new config and a guaranteed
AES-256 key length.

**Alternatives considered**:
- *Fernet* — convenient but it is **AES-128-CBC + HMAC**; using it would violate the explicit "AES-256"
  requirement. **Rejected.**
- *AES-256-CBC + separate HMAC* — unauthenticated unless paired carefully; GCM gives AEAD in one step.
  Rejected.
- *A fixed/derived nonce* — nonce reuse under GCM is catastrophic; random-per-op is required. Rejected.

---

## D4 — Encrypt originals only; HMAC-keyed forward field names; fakes as the clear reverse index

**Decision**: Per spec clarification Q1, only the **original** value is encrypted (D3). The synthetic
**fake** is not personal data, so it is stored in clear and used directly as the reverse-lookup index. To
keep original PII out of Redis field *names*, the forward field name is a **keyed HMAC** —
`"fwd:" + HMAC_SHA256(key, type + "|" + mapping_key)` (hex) — where `mapping_key` is the per-type
normalized form (D5). The original value appears **only** inside an encrypted field value (in the `rev:`
records). Concretely, per mapping:
- `fwd:{hmac}` → `enc(fake_base)`
- `rev:{fake_form}` → `enc(json{orig_base, case, entity_type})` — one `rev:` field per inflected fake form
- `forms:{fake_base}` → `enc(json{case: fake_form, …})`

**Rationale**: HMAC keyed with the system key (never exposed) keeps the forward index non-reversible
*and* resistant to offline dictionary/brute-force — critical because identifier domains are tiny (a PESEL
is 11 digits; an unkeyed SHA-256 of it is trivially precomputed). This strengthens the user's suggested
plain SHA-256 while honoring "logs and stored keys never contain original PII in readable form" (FR-026)
and the Q1 clarification. Fakes in clear make `get_original` a direct `rev:` field read.

**Alternatives considered**:
- *Plain SHA-256 of the normalized original as the field name* — non-reversible but **precomputable** for
  small domains (PESEL/NIP/phone); weaker. Rejected in favor of keyed HMAC.
- *Deterministic encryption of both sides so ciphertext is the index* — exposes equality and needs a
  separate AEAD scheme; more complex, weaker than randomized GCM + HMAC index. Rejected (and contradicts
  Q1, which keeps fakes in clear).
- *Encrypting the fake too* — unnecessary (synthetic, not PII) and would break direct reverse lookup.
  Rejected.

---

## D5 — One Redis HASH per session; single sliding TTL; default 30 min

**Decision**: One Redis **HASH** per session at key `session:{session_id}` holding all `fwd:`/`rev:`/
`forms:` fields plus a single `meta` field (`enc(json{created_at, last_activity, entity_count,
message_count})`). A single `EXPIRE session:{id} <ttl>` governs the whole session; **every successful
`MappingStore` operation refreshes it** (sliding expiry — FR-009). `get_all_mappings` is one `HGETALL` +
decrypt; `delete_session` is one `DEL` (atomic clear — FR-010); listing is one `HGETALL` (FR-011). TTL is
`settings.redis_session_ttl`, whose **default is changed 3600 → 1800** to honor the clarified 30-minute
default (FR-009); env override still applies. Because this path requires Redis, the routes are **not**
added to `main.py`'s `_GATE_EXEMPT_PATHS`, so Epic 1's middleware 503s them automatically when Redis is
down — no gate code change.

**Rationale**: A single hash gives atomic whole-session clear and expire, single-round-trip listing, and a
natural place for the meta. Sliding TTL on every op implements "activity refreshes expiry" without extra
bookkeeping. Reusing the existing gate keeps Redis-dependency behavior consistent with Epic 1 (FR-027 loss
on restart is acceptable and tested).

**Alternatives considered**:
- *One Redis key per mapping with individual TTLs* — no atomic clear, many round-trips for listing, and
  per-key expiry can't express "any activity refreshes the *session*". Rejected.
- *A separate `meta` key* — splits the lifecycle across keys; folding meta into the hash keeps one `DEL`/
  one `EXPIRE`. Rejected.

---

## D6 — Collision-free generation: store-owned retry + per-type fallback

**Decision**: The generator is **stateless** (knows nothing of the session), so collision avoidance lives
in `MappingStore.get_or_create`. On generating a candidate fake whose base/any-form already exists as a
`rev:`/`forms:` value in the session, the store **re-invokes the generator up to 3 times**. If still
colliding, it applies a **per-type deterministic fallback**: a numeric suffix for IDs/email/phone
(re-generate digits / append before the `@`), and a **re-roll (never a suffix) for PERSON/LOCATION names**
— an unrealistic suffix on a name would violate Constitution VII. The result is guaranteed unique within
the session (FR-015).

**Rationale**: Keeping the generator pure makes it trivially unit-testable with a seed; the store is the
only component that knows what's "already in use". Names must stay realistic, so they re-roll rather than
gain a digit.

**Alternatives considered**:
- *Stateful generator that tracks used values* — couples generation to a session and breaks seed-based
  reproducibility. Rejected.
- *Always suffix on collision* — simple but produces `Kowalski2`, violating realistic substitution.
  Rejected for names.

---

## D7 — Coreference: exact key, then same-type full-lemma containment; ambiguous → new

**Decision**: `get_or_create` first checks the exact forward key (D4/D5). On a miss, **for PERSON/LOCATION
only**, it resolves inflected/partial references before generating: decrypt the session's existing
originals **of the same `entity_type`** and test the new entity's `lemma` for **full-token containment**
against them (e.g. lemma `"Kowalski"` is contained in stored `"Jan Kowalski"`), matching on whole name
tokens — never on shared fragments, so "Anna Kowalska" and "Jan Kowalski" stay distinct (FR-014). If
**exactly one** existing person matches, reuse its fake; if **two or more** match (e.g. both "Jan
Kowalski" and "Adam Kowalski" are present and the new mention is bare "Kowalski"), treat it as a **new,
separate person** and generate a fresh fake — the system never guesses (spec clarification Q2). Scoped
strictly within one entity type (cross-type same literal = two mappings, FR-025).

**Rationale**: Implements FR-013 (full-name → surname-only reuse) without the false merges that fragment
matching causes, and encodes the Q2 tie-break deterministically (testable). Containment over **lemmas**
(from D1) is inflection-robust because both sides are base forms.

**Alternatives considered**:
- *Substring/fragment matching on raw text* — merges distinct same-root people and inflected noise.
  Rejected.
- *Resolve ambiguous surname to most-recent / earliest match* — silently misattributes data to the wrong
  person in legal text. Rejected per Q2.

---

## D8 — Fuzzy restore via pure-Python bounded Levenshtein (≤2)

**Decision**: `get_original` first does an exact `rev:{fake_form}` lookup; on a miss it scans the session's
`rev:` field names and accepts the closest within **edit distance ≤ 2**, computed by a small
**pure-Python bounded** Levenshtein (early-exit once the band is exceeded). No new dependency.

**Rationale**: A fake may surface (especially in Epic 4, from an LLM) in an inflected form the generator
didn't pre-compute among `all_forms`; a tight edit-distance tolerance recovers it without over-matching.
A bounded implementation is cheap at session scale, and avoiding a C-extension (`rapidfuzz`/
`python-Levenshtein`) keeps the dependency surface minimal (Constitution IX).

**Alternatives considered**:
- *`rapidfuzz` / `python-Levenshtein`* — fast C libs, but an unnecessary native dependency for a tiny
  bounded check at this scale. Rejected.
- *Unbounded fuzzy / token-set ratio* — risks matching the wrong fake; the ≤2 band is deliberately tight.
  Rejected.

---

## D9 — Dates: uniform ±10-year shift, `DD.MM.YYYY`

**Decision**: `pseudonym_generation/builders/date_pl.py` shifts **every** `DATE_TIME` fake within **±10 years** of
the parsed original and renders `DD.MM.YYYY`. No attempt is made to classify a date as a birth date.

**Rationale**: Spec clarification Q4 — reliable DOB identification is hard, and a ±10-year window keeps any
date (birth date or contract date) plausible while removing a fragile classifier (Constitution IX).

**Alternatives considered**:
- *Classify DOB via PESEL-derived date or context words, then branch the window* — adds an unreliable
  classifier for marginal benefit. Rejected per Q4.

---

## Resolved unknowns summary

| Spec assumption / unknown | Resolved by |
|---|---|
| Which fields are encrypted; how reverse lookup works on encrypted data | D3 + D4 (originals only; HMAC forward index; clear fakes as reverse index) |
| Exact index/serialization mechanics (HMAC choice) | D4 (HMAC-SHA256 keyed with the system key) |
| TTL default & refresh granularity | D5 (1800s default, sliding refresh on every op) |
| Coreference matching rule + ambiguous tie-break | D7 (same-type full-lemma containment; ambiguous → new) |
| Restore "locate fake forms incl. inflected" mechanism | D4 `forms`/`rev` + D8 bounded fuzzy |
| Realistic-substitution toolchain | Faker `pl_PL` + checksum generators (D6, generators.md) |
| Inflection scope / method | D1 (original base+case from spaCy) + D2 (generate-only suffix tables) |
| Date faking | D9 (uniform ±10y, DD.MM.YYYY) |
| Redis gating of the new routes | D5 (non-exempt → Epic 1 gate applies, no code change) |

No open NEEDS CLARIFICATION items remain for Phase 1.
