# Data Model: EPIC 4 — Anonymization Pipeline & First LLM Round-Trip

**Feature**: `specs/005-anonymization-pipeline` | **Date**: 2026-06-17

EPIC 4 introduces **no new persisted data** — the Redis field layout and the AES-256-GCM envelope are
frozen (regression contract). The entities below are in-memory/transport models and component
contracts. Reused EPIC 2/3 types (`DetectedEntity`, the Redis `fwd:/rev:/forms:/meta` schema,
`MappingStore`) are unchanged and only referenced.

---

## 1. Transport models (chat surface)

### ChatMessage
One message in an OpenAI-compatible conversation.

| Field | Type | Notes |
|-------|------|-------|
| `role` | `str` | `"user"` / `"assistant"` / `"system"`. |
| `content` | `str` | Free text. The inbound stage pseudonymises this field. |

### ChatCompletionRequest
| Field | Type | Rules |
|-------|------|-------|
| `messages` | `list[ChatMessage]` | MUST be non-empty (else 400). Last element MUST have `role == "user"` (else 400). |
| `session_id` | `str \| None` | Absent/blank → a new id is generated and returned. |
| `model` | `str \| None` | Optional; falls back to `settings.default_model`. |

### ChatCompletionResponse (minimal, OpenAI-shaped)
| Field | Type | Notes |
|-------|------|-------|
| `session_id` | `str` | The id used; echoed so the caller can continue the conversation. |
| `choices` | `list[Choice]` | Exactly one element this epic. |

`Choice = {index: int, message: ChatMessage(role="assistant"), finish_reason: None}`. `usage`, real
`finish_reason` passthrough, and anonymisation metadata are **deferred** (later epic).

### ChatErrorBody
Returned with 400/503/504. `{detail: str, session_id: str}` — `session_id` is always present on
503/504 (preserved across the failed LLM call); 400 includes it when one was supplied/derived.

---

## 2. AnonymizationPipeline (internal component)

Programmatically callable orchestrator (FR-001). Constructed with the reused collaborators; no HTTP
dependency.

**Construction**: `AnonymizationPipeline(engine: DetectionEngine, store: MappingStore)`.

**Methods**:

| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `pseudonymize_text` | `async (session_id, text) -> (fake_text, list[Replacement])` | The extracted EPIC 3 inbound core (D8): detect → `store.get_or_create` per entity → reverse-order splice. Empty/whitespace → `(text, [])`. |
| `pseudonymize_messages` | `async (session_id, messages) -> list[ChatMessage]` | Applies `pseudonymize_text` to **every** message's `content` each turn (FR-005); roles preserved; deterministic via session consistency (FR-006). |
| `depseudonymize_text` | `async (session_id, text) -> str` | Outbound stage: `store.restore_text(session_id, text, fuzzy=True)` — exact + inflection first, then fuzzy fallback (FR-004). |

`Replacement = {entity_type, original, fake, start, end}` (offsets into the ORIGINAL text) — identical
to the existing `api/pseudonymize.Replacement`, now produced centrally.

**Invariant (FR-024, Constitution I/VIII)**: after `pseudonymize_messages`, no message `content`
contains any original value held in the session mapping; logs emit only `session_id`, entity
types/counts, timings.

---

## 3. FuzzyNameRestorer (new pure collaborator, `pseudonym_vault/fuzzy_restoration.py`)

Outbound fallback over text the exact pass left (D1–D4). Pure: caller supplies the name-type reverse
records; no Redis.

**Input per call**: `text: str`, `name_records: list[NameFake]` where
`NameFake = {fake_forms: list[str], orig_base: str, fake_base: str, entity_type}` derived from
`reverse_records` filtered to `{PERSON, LOCATION}`.

**Algorithm** (parameters frozen — research D3):
1. Split `text` into word-boundary tokens; keep non-token separators to reassemble verbatim.
2. For each token with `len ≥ 4` that the exact pass did not already replace:
   - Build the candidate set: every token of every `fake_forms` surface across `name_records`.
   - Keep only candidates sharing a prefix `L ≥ 0.6 × len(shorter)` with the token (prefix anchor).
   - Among those, keep candidates with `bounded_levenshtein(token, candidate, 2) is not None`.
   - Pick the minimum-distance candidate; if two candidates from **different originals** tie at the
     minimum, **skip** the token (FR-013).
   - On a unique best, replace the token with the **aligned original token** in nominative form (D4).
3. Reassemble and return.

**Guarantees**: PERSON/LOCATION only (FR-009); never matches a token < 4 (FR-010); prefix anchor +
distance ≤ 2 reject look-alikes and invented names (FR-011/FR-012/FR-015); deterministic, tie → skip
(FR-013); restores base/nominative form (FR-014).

---

## 4. LLM provider port (`llm_providers/`)

### LLMProvider (abstract — `base.py`)
| Member | Signature | Notes |
|--------|-----------|-------|
| `complete` | `async (messages: list[ChatMessage], *, model: str) -> str` | Returns assistant text; raises `LLMProviderError` on failure. |
| `health_check` | `async () -> bool` | Lightweight reachability probe; implemented + tested but **not consumed this epic** (503 is driven by `complete()` raising) — reserved for the future `/health`. |

### LLMProviderError (`base.py`)
`Exception` with `kind: Literal["unreachable", "missing_model", "timeout"]` and a readable message.
Maps to HTTP per research D6.

### OllamaProvider (`ollama_provider.py`)
Concrete REST adapter. `POST {OLLAMA_BASE_URL}/api/chat` `{model, messages, stream: false}`, timeout
`OLLAMA_TIMEOUT`; reads `message.content`. `health_check` → `GET /api/tags`. Exception mapping:
`ConnectError/ConnectTimeout → unreachable`; non-2xx "model not found"/404 → `missing_model`;
`ReadTimeout/TimeoutException → timeout`.

### EchoProvider (`echo_provider.py`)
Deterministic, network-free. `complete` returns a fixed transform of the conversation (e.g. the last
user message's content, optionally prefixed) so round-trip tests can assert restoration without a real
model. `health_check` → `True`.

---

## 5. Configuration delta (`config.py`)

| Setting | Env var | Default | Status |
|---------|---------|---------|--------|
| `ollama_base_url` | `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | exists |
| `ollama_timeout` | `OLLAMA_TIMEOUT` | `60.0` | **new** |
| `default_model` | `DEFAULT_MODEL` | `gpt-4o` | exists (operator sets an Ollama model for the demo) |
| `default_llm_provider` | `DEFAULT_LLM_PROVIDER` | `openai` | exists (router is a later epic; this epic wires Ollama directly) |

No change to `redis_*` or `redis_encryption_key`.

---

## 6. Reused / frozen (referenced, not modified)

- `DetectedEntity` (`pii_detection/dto.py`) — `entity_type, start, end, score, text, metadata, lemma,
  case`.
- `DetectionEngine.detect()` / `nlp.is_model_ready()` — detection, unchanged.
- `MappingStore` facade — `get_or_create`, `restore_text` (**+ new opt-in `fuzzy` param, default
  `False`**), `get_original`, `get_all_mappings`, `delete_session`, `extend_ttl`. The only change is
  the additive `fuzzy` parameter and an internal call into `FuzzyNameRestorer`; the Redis
  `fwd:/rev:/forms:/meta` layout and the AES-256-GCM envelope are unchanged.
- `bounded_levenshtein`, `CoreferenceResolver`, `OriginalSurfaceRestorer`,
  `SessionMappingRepository.reverse_records` — reused by the fuzzy pass.
