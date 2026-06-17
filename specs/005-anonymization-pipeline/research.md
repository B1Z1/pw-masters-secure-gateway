# Research: EPIC 4 — Anonymization Pipeline & First LLM Round-Trip

**Feature**: `specs/005-anonymization-pipeline` | **Date**: 2026-06-17

This document resolves the design unknowns for EPIC 4. The stack is fixed (Constitution
Technology Constraints); no alternatives to Python 3.12 / FastAPI / async redis / httpx / Faker /
Presidio are evaluated. Each decision records what was chosen, why, and the alternative rejected.

---

## D1 — Where the outbound fuzzy fallback lives

**Decision**: Add an **opt-in `fuzzy: bool = False` parameter** to `MappingStore.restore_text`, and
implement the prefix-anchored token pass in a new pure collaborator
`gateway_api/pseudonym_vault/fuzzy_restoration.py` (`FuzzyNameRestorer`). The pipeline's outbound
stage calls `store.restore_text(session_id, text, fuzzy=True)`; the EPIC 3 `/v1/depseudonymize`
handler keeps calling `restore_text(session_id, text)` (fuzzy off).

**Rationale**:
- The exact + inflection pass already lives in `restore_text`, and the candidate data
  (`SessionMappingRepository.reverse_records`), the distance primitive (`bounded_levenshtein`), and
  the surface logic (`OriginalSurfaceRestorer`) are all already in `pseudonym_vault`. Co-locating the
  fuzzy pass keeps the linguistic/restoration logic in one package and the pipeline thin.
- **Default-off preserves the regression contract byte-for-byte**: `/v1/depseudonymize` and every
  existing `test_mapping_store` restore test call `restore_text` with no flag, so EPIC 3 behaviour,
  the Redis field layout, and the AES-256-GCM envelope are untouched. The new path is reachable only
  via `fuzzy=True` (pipeline + chat + new tests).

**Alternatives rejected**:
- *Fuzzy entirely inside the pipeline outbound stage.* Would require a new public store method to
  expose name-type reverse records and would re-implement tokenization that belongs next to the exact
  pass. More surface, same risk, worse cohesion.
- *Always-on fuzzy in `restore_text`.* Violates the regression contract — it would change
  `/v1/depseudonymize` output for look-alike inputs.

---

## D2 — Fuzzy candidate set: match against stored fake **forms**, not just bases

**Decision**: The fuzzy pass matches answer tokens against the **tokens of every stored fake surface
form** for PERSON/LOCATION (i.e. the `reverse_records` keys: base + every per-case form that EPIC 3
pre-wrote, plus exact-captured surfaces), scoped to `entity_type ∈ {PERSON, LOCATION}` via the
reverse record. On a hit it restores the **original in nominative/base form** (token-aligned — see
D4).

**Rationale**: An "unforeseen" inflected form produced by a real LLM is almost always within ≤ 2
edits of the *nearest known case form*, even when it is > 2 edits from the bare nominative base (Polish
oblique suffixes like `-iem`, `-owi`, `-ego` add 2–4 characters). Matching against the full stored
form set — which `reverse_records` already returns — keeps `max_distance = 2` realistic. `get_original`
already demonstrates this pattern (fuzzy loop over `reverse_records`); EPIC 4 generalises it from a
single-fake lookup to a token pass over the whole answer and adds the prefix anchor + type scope.

**Alternatives rejected**: Matching only against the nominative base would force a larger
`max_distance` (≥ 4) to catch common oblique cases, which would start matching genuinely different
names — unsafe.

---

## D3 — Fuzzy algorithm parameters (frozen for this epic)

| Parameter | Value | Source / note |
|-----------|-------|---------------|
| Entity scope | **allowlist `{PERSON, LOCATION}`** | All other types are exact-only by default (robust to label spelling). |
| Exact-only types | `PESEL, NIP, REGON, IBAN, POLISH_BANK_ACCOUNT, NRB, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME, POLISH_ADDRESS, ORGANIZATION`, and any future type | A one-char edit on a PESEL is a different valid number; identifiers/contacts are never fuzzy. |
| Ordering | exact + inflection pass **first**, fuzzy **only** on text the exact pass left | `restore_text` exact loop runs unchanged, then the fuzzy pass. |
| Never re-touch | a span already replaced with an original is never matched again | Fuzzy matches fake-form tokens; restored spans hold originals, not fakes. |
| Tokenization | word-boundary, `(?<!\w)…(?!\w)` semantics, per whitespace/punctuation token | Mirrors the word-boundary regex `restore_text` already uses. |
| Min token length | **4** | Shorter tokens are skipped entirely. |
| Prefix anchor | shared common prefix `L ≥ 0.6 × len(shorter token)` **before** distance is computed | Polish inflection changes the suffix, not the stem; this is the primary guard and the "length-aware" gate (short tokens need a proportionally longer shared stem). |
| Distance gate | `bounded_levenshtein(token, fake_token, max_distance=2)` is **not None** | Final gate after the prefix anchor; reuses the existing early-exit band. |
| Best match | minimum edit distance; on an **unresolvable tie** (two distinct originals equally close) **skip** | Deterministic; never guess. |
| Restored form | original in **base/nominative** form (token-aligned, D4) | Documented limitation: identity correct, surrounding grammar may be slightly off (Constitution IX). |
| Invented names | left untouched | The prefix anchor + distance gate reject tokens with no stored fake near them. |

"Length-aware" is realised by the prefix-anchor ratio (0.6 × shorter length), not by a per-length
distance table — keeping the gate simple while making short tokens harder to match.

---

## D4 — Token alignment on a fuzzy hit (which original token to restore)

**Decision**: For each name fake, precompute a **fake-token → original-token** alignment by zipping
`fake_base.split()` with `orig_base.split()` when the token counts match; restore the aligned original
token (nominative). When counts differ (hyphen-split, multi-word city), fall back to replacing the
single matched token with the whole `orig_base`.

**Rationale**: Lets "…Nowakiem…" (instrumental of fake surname *Nowak* for original *Kowalski*)
restore to "…Kowalski…" rather than the full "Jan Kowalski". Reuses the spirit of the existing
`aligned_fake` helper. The fallback guarantees identity is still restored when alignment is unclear,
honouring the documented base-form limitation.

---

## D5 — LLM provider port shape

**Decision**: `gateway_api/llm_providers/base.py` defines an abstract `LLMProvider` with:
- `async def complete(self, messages: list[ChatMessage], *, model: str) -> str` — returns assistant
  text;
- `async def health_check(self) -> bool` — lightweight reachability probe;
and an `LLMProviderError(Exception)` carrying a discriminator
`kind: Literal["unreachable", "missing_model", "timeout"]`. `ChatMessage` is a small pydantic model
`{role: str, content: str}` (OpenAI-compatible).

**Rationale**: Matches Constitution IV (pipeline depends on the interface, never a concrete provider;
a new provider needs no pipeline change). The single `LLMProviderError.kind` keeps error→HTTP mapping
in one place (D6). `model` is passed per call so the future model router (later epic) drops in without
touching the port.

**Note on `health_check`**: it is part of the port (FR-016 requires a reachability check) and is
implemented + unit-tested this epic, but it is **not consumed** by the chat path. The 503
unreachable/missing-model response is driven by `complete()` raising `LLMProviderError` (D6), not by a
pre-flight probe; `health_check` is **reserved for the future `/health` integration**. This is
deliberate, not dead code.

**Alternatives rejected**: Returning a rich response object (usage, finish_reason) — deferred to the
later "full chat response contract" epic; this epic returns plain text.

---

## D6 — Error taxonomy → HTTP status

**Decision**: In `api/chat.py`:

| Condition | Detected as | HTTP |
|-----------|-------------|------|
| empty `messages` / last message not `role == "user"` | request validation, **before** any LLM call | **400** |
| Ollama unreachable (connection refused/DNS) | `httpx.ConnectError` / `ConnectTimeout` → `kind="unreachable"` | **503** |
| model missing (Ollama 404 / "model not found") | non-2xx body parsed → `kind="missing_model"` | **503** |
| LLM call exceeds `OLLAMA_TIMEOUT` | `httpx.ReadTimeout` / `TimeoutException` → `kind="timeout"` | **504** |

Every error response **echoes `session_id`** (generated before the LLM call) and a readable `detail`.

**Rationale**: Directly satisfies spec FR-021/FR-022 and the acceptance bullets. Validation that needs
no LLM happens first, so malformed requests never reach Ollama.

---

## D7 — Ollama REST adapter

**Decision**: `OllamaProvider.complete` issues `POST {OLLAMA_BASE_URL}/api/chat` with
`{"model": model, "messages": [{"role","content"}…], "stream": false}` via a shared async
`httpx.AsyncClient` with `timeout=OLLAMA_TIMEOUT`; reads `response.json()["message"]["content"]`.
`health_check` issues `GET {OLLAMA_BASE_URL}/api/tags` (or `/api/version`) and returns whether it is
2xx. Exceptions map per D6. `stream=False` enforces Constitution V (full answer before
de-pseudonymisation).

**Rationale**: `/api/chat` is Ollama's native multi-turn endpoint and maps 1:1 to our messages array.
`httpx` is already a dependency — no new package. Base URL already defaults to
`http://host.docker.internal:11434` in `Settings`.

**New config**: add `ollama_timeout: float = 60.0` (`OLLAMA_TIMEOUT`) to `Settings`. `ollama_base_url`
and `default_model` already exist; the model name is taken from the request `model` field when present,
else `settings.default_model` (operator sets it to an installed Ollama model for the live demo).
`DEFAULT_LLM_PROVIDER` is **not consulted this epic** — `get_llm_provider()` returns the Ollama adapter
directly; the model-based provider router that would honour it is a later epic.

---

## D8 — Inbound stage: extract, do not duplicate

**Decision**: Move the substitution body currently inline in `api/pseudonymize.py::pseudonymize`
(detect → `store.get_or_create` per entity → reverse-order splice → build `Replacement` list) into
`AnonymizationPipeline.pseudonymize_text(session_id, text) -> (fake_text, replacements)`. The EPIC 3
handler is refactored to call it; the chat path calls `pseudonymize_messages`, which applies
`pseudonymize_text` to **every message's content** each turn (FR-005). The model-ready/Redis-store
gating stays in the handlers.

**Rationale**: FR-003 requires a single shared implementation. Because `get_or_create` is already
session-consistent, applying it across the whole array yields deterministic re-pseudonymisation
(FR-006) for free; no new mapping logic. The handler refactor must preserve the exact
`PseudonymizeResponse` shape (offsets into the ORIGINAL text, ordering) so `test_pseudonymize_api`
stays green.

**Alternatives rejected**: Leaving the logic inline and re-implementing it in the pipeline — explicitly
forbidden by FR-003 and the brief.

---

## D9 — Endpoint shape & Redis gate

**Decision**: `POST /v1/chat/completions` in `api/chat.py`, included in `main.py` **without** adding to
`_GATE_EXEMPT_PATHS`, so the EPIC 1 `redis_availability_gate` 503s it when Redis is down (it needs the
store). Request `{messages: [{role,content}], session_id?, model?}`; response
`{session_id, choices: [{index, message: {role:"assistant", content}, finish_reason: null}]}` —
OpenAI-compatible in *shape*, minimal in *content*. `session_id` is `request.session_id or
uuid.uuid4().hex` (mirrors `/v1/pseudonymize`).

**Rationale**: Reuses the existing gate exactly as the EPIC 3 routes do; no new middleware. The
`choices` array gives OpenAI shape now; `usage`, real `finish_reason` passthrough, and anonymisation
metadata are the later "full response contract" epic.

---

## D10 — Testing strategy (no network in CI)

**Decision**:
- **Pipeline round-trip**: `EchoProvider` (returns a deterministic transform of the last user message,
  e.g. echoes the pseudonymised content) drives `pseudonymize → provider → depseudonymize` with no
  network; asserts originals restored and that the messages handed to the provider contain **no
  original PII**.
- **Fuzzy unit tests** (`tests/pseudonym_vault/test_fuzzy_restoration.py`): inflected PERSON/LOCATION
  recovery in base form; exact-only enforcement (a perturbed PESEL/IBAN/EMAIL_ADDRESS is *not*
  fuzzed); prefix-anchor rejection of a look-alike non-PII token; invented-name passthrough;
  tie-skip determinism; already-restored span untouched.
- **Chat endpoint** (`tests/test_chat_api.py`): happy path with a stub provider via FastAPI
  dependency override + `fakeredis`; 400 (empty array / non-user last message); 503 (provider
  `kind="unreachable"`/`"missing_model"`); 504 (`kind="timeout"`); `session_id` preserved in every
  error body.
- **No-PII assertions**: capture the provider's received payload and `caplog`; assert no original
  value appears in either (FR-024, Constitution VIII).

**Rationale**: `pytest-asyncio` is in `asyncio_mode = "auto"` and `fakeredis` is already a dev
dependency, so store-backed tests run offline. The `EchoProvider`/stub keep the suite deterministic
and network-free, satisfying spec FR-027.
