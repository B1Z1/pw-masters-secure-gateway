# Data Model: EPIC 6 — API Gateway Finalization

**Feature**: `specs/007-api-gateway-finalization` | **Date**: 2026-06-18

EPIC 6 introduces **no new persisted data** — the Redis `fwd:/rev:/forms:/meta/corefs` layout and the
AES-256-GCM envelope are **frozen** (§7). It begins *incrementing* the already-defined
`SessionMeta.message_count` and *reading* `created_at`/`last_activity`/the live TTL. The new models are
**transport** (the full chat response + the provider/session response shapes) and two small internal
value objects (`CompletionResult`, `InboundResult`); the changes to the provider port, the pipeline,
and the store/repository are listed as **deltas**. Reused EPIC 2/3/5 types
(`DetectedEntity`, `MappingStore` internals, the adapters, `LLMRouter`, `Replacement`) are referenced,
not redefined.

---

## 1. Chat transport models (`api/chat.py`) — full contract

### Request (permissive — D6)

| Model | Fields | Notes |
|-------|--------|-------|
| `ChatInputMessage` | `role: str \| None = None`, `content: Any = None` | **Permissive** so bad input is a handler 400 (with `session_id`), not a pre-handler 422. |
| `ChatCompletionRequest` | `messages: list[ChatInputMessage]`, `session_id: str \| None = None`, `model: str \| None = None` | Validated manually in order (D6); valid messages → `ChatMessage`. |

### Response (success)

| Model | Fields |
|-------|--------|
| `ChatMessageOut` | `role: str` (`"assistant"`), `content: str` |
| `Choice` | `index: int` (`0`), `message: ChatMessageOut`, `finish_reason: str` (normalized — **now always a string**, D2) |
| `TimingBreakdown` | `ner_analysis: float`, `fake_generation: float`, `redis_write: float`, `llm_request: float`, `deanonymization: float`, `total: float` (all **ms**) |
| `AnonymizationMeta` | `entities_detected: dict[str, int]`, `total_entities: int`, `provider: str`, `model: str`, `processing_time_ms: float`, `timing_ms: TimingBreakdown` |
| `InputAnonymization` | `pseudonymized_content: str`, `replacements: list[Replacement]` (reused pipeline model; offsets into the **original** latest user message) |
| `ChatCompletionResponse` | `id: str` (`"chatcmpl-"+uuid4().hex`), `object: str` (`"chat.completion"`), `created: int` (unix s), `model: str` (resolved, un-stripped), `choices: list[Choice]`, `session_id: str`, `anonymization_meta: AnonymizationMeta`, `input_anonymization: InputAnonymization` |

### Error (unchanged from EPIC 4/5)

`_error(status, detail, session_id)` → `{"detail": str, "session_id": str}`. Statuses from the reused
`_ERROR_STATUS` map (§5). **Every** chat error body preserves `session_id` (FR-010).

**Validation rules (D6), all before any provider call, each → `_error(400, …, session_id)`**:
1. `messages` non-empty; 2. each message `role ∈ {system,user,assistant}` and `content` is a
non-`None` `str`; 3. last message role == `user`; 4. router `unknown_model` → 400 listing prefixes.

---

## 2. Provider port delta (`llm_providers/base.py`) — FR-022

### `CompletionResult` — NEW (return type of `complete`)

```text
@dataclass(frozen=True)
class CompletionResult:
    content: str         # assistant text (de-pseudonymized downstream)
    finish_reason: str   # normalized OpenAI vocab: "stop" | "length"  (D2)
    provider: str        # "openai" | "anthropic" | "ollama" | "echo"
```

### `normalize_finish_reason(raw: str | None) -> str` — NEW (single mapping, D2)

`stop`/`length` → same; `end_turn`/`stop_sequence` → `stop`; `max_tokens` → `length`; everything else /
`None` → `stop`.

### `LLMProvider.complete` — SIGNATURE CHANGED

`async complete(messages: list[ChatMessage], *, model: str) -> CompletionResult` (was `-> str`).
`health_check()`, `ChatMessage`, `LLMProviderError`, and `ProviderErrorKind` are **unchanged**.

### Adapter returns (each constructs `CompletionResult`)

| Adapter | content | raw finish reason → normalized | provider |
|---------|---------|--------------------------------|----------|
| `OpenAIProvider` | `choices[0].message.content or ""` | `choices[0].finish_reason` | `"openai"` |
| `AnthropicProvider` | joined text blocks | `response.stop_reason` | `"anthropic"` |
| `OllamaProvider` | `message.content` | `response.json().get("done_reason")` (absent → `None`) | `"ollama"` |
| `EchoProvider` | last user message | `None` → `"stop"` | `"echo"` |
| `LLMRouter` | — (pass-through) | — (pass-through) | — (inner adapter's) |

The OpenAI length-truncation **warning + partial content** behaviour is reused unchanged; the adapter
now *also* surfaces the normalized `length`.

---

## 3. Pipeline delta (`pipeline/anonymization_pipeline.py`) — FR-015/FR-005/FR-006

### `InboundResult` — NEW

```text
@dataclass
class InboundResult:
    fake_messages: list[ChatMessage]
    entities_detected: dict[str, int]          # per-type counts over the WHOLE history
    total_entities: int
    last_user_pseudonymized: str
    last_user_replacements: list[Replacement]  # offsets into the ORIGINAL latest user message
    timing: InboundTiming
```

`InboundTiming` = `{ner_analysis_ms: float, fake_generation_ms: float, redis_write_ms: float}` (D4).

### Methods

| Method | Status | Behaviour |
|--------|--------|-----------|
| `run_inbound(session_id, messages) -> InboundResult` | **NEW** (replaces `pseudonymize_messages`) | One inbound pass over the whole history reusing `pseudonymize_text` per message; aggregates per-type counts (per detected occurrence per message), captures the **last** message's synthetic text + replacements, and records the three inbound timing stages (D4). |
| `pseudonymize_text(session_id, text) -> (fake_text, replacements)` | **UNCHANGED** | Still used by `run_inbound` and the debug `/v1/pseudonymize`. |
| `depseudonymize_text(session_id, text) -> str` | **UNCHANGED** | Outbound restore (timed as `deanonymization` by the endpoint). |
| `pseudonymize_messages(...)` | **REMOVED** | Sole caller (chat endpoint) moves to `run_inbound`. |

`Replacement{entity_type, original, fake, start, end}` is **reused** as both the pipeline output and the
`input_anonymization.replacements` item.

---

## 4. Store / repository deltas (`pseudonym_vault/`) — additive, signatures elsewhere unchanged

### `SessionMappingRepository` (`session_mapping_repository.py`)

| Member | Status | Behaviour |
|--------|--------|-----------|
| `read_meta(session_id) -> dict \| None` | **NEW** | Decrypt the `meta` field; `None` when absent. |
| `ttl_seconds(session_id) -> int` | **NEW** | `await redis.ttl(key)` (Redis: `-2` missing, `-1` no-expire). |
| `delete(session_id) -> bool` | **CHANGED** | Now returns `await redis.delete(key) == 1` (*existed*); previously returned `None`. |
| `bump_message_count(session_id) -> None` | **NEW** | Read `meta`; if present, write back `message_count + 1` (preserving other fields); **no-op when `meta` is absent** (never creates a hash) — D7. |
| inbound redis-write timing hook | **NEW (internal)** | The write methods (`write_mapping`, `write_exact_reverse`, `append_coref`, `bump_meta`, `extend_ttl`) add their Redis-call duration to the active inbound `redis_write` sink contextvar when set; zero-cost no-op otherwise (D4). |
| `bump_meta` | **UNCHANGED** | Still increments `meta.entity_count` per mapping write (a write counter — not the dashboard's distinct count). |

### `MappingStore` (`mapping_store.py`)

| Member | Status | Behaviour |
|--------|--------|-----------|
| `get_session_summary(session_id) -> dict \| None` | **NEW** | `read_meta` (→ `None` ⇒ caller 404); group `get_all_mappings` by `entity_type` into `entities_by_type`; `entity_count` = sum; attach `created_at`/`last_activity`/`message_count` from meta and `ttl_remaining_seconds` from `ttl_seconds`. |
| `increment_message_count(session_id) -> None` | **NEW** | Delegates to `repository.bump_message_count` (D7). |
| `delete_session(session_id) -> bool` | **CHANGED** | Delegate to `repository.delete` (now → `bool`) and discard the in-process session lock; return *existed*. |
| `get_all_mappings(session_id) -> list[dict]` | **UNCHANGED** | Distinct original↔fake pairs (`entity_type`, `original`, `fake`) — the source for `entities_by_type`. |

---

## 5. Error taxonomy → HTTP (reused, unchanged)

The EPIC 5 single map in `api/chat.py` is reused verbatim:

```text
_ERROR_STATUS: dict[ProviderErrorKind, int] = {
    "unreachable": 503, "missing_model": 503, "timeout": 504,
    "rate_limit": 429, "auth": 503, "unknown_model": 400,
}
# status = _ERROR_STATUS.get(exc.kind, 503); every error body preserves session_id.
```

`auth` 503 names the missing key; `unknown_model` 400 lists the recognized prefixes. No new kinds.

---

## 6. Provider & session response shapes (new endpoints)

### `GET /v1/providers` (`api/providers.py`) — D9

`list[ProviderDescriptor]` where `ProviderDescriptor = {name: str, requires_key: bool,
key_configured: bool}`. Fixed three entries: `openai`(true, `bool(openai_api_key)`),
`anthropic`(true, `bool(anthropic_api_key)`), `ollama`(false, false). **No key value** is ever included.

### `GET /v1/sessions/{session_id}` (`api/sessions.py`) — D8

`SessionSummaryResponse = {session_id: str, created_at: str, last_activity: str,
ttl_remaining_seconds: int, entity_count: int, entities_by_type: dict[str,int], message_count: int}`.
404 (`{"detail": …}`) when no stored state.

### `DELETE /v1/sessions/{session_id}` — D8

Success (`{"session_id": str, "deleted": true}` / 200) only when the session existed; otherwise 404.

---

## 7. Observability models (`observability/`) — D4/D10/D11

| Type | Where | Shape / role |
|------|-------|--------------|
| `RequestMetrics` | `request_metrics.py` | Request-scoped accumulators for the six stages + helpers (`time_stage(name)`); finalizes the `timing_ms` dict and `processing_time_ms`. Lives on `request.state`. |
| inbound redis-write sink | `request_metrics.py` | A `contextvars.ContextVar` the pipeline sets only around inbound persistence so the repository's write durations land in `redis_write` (not outbound) — D4. |
| structured log record | `request_logging.py` (emitted, not a stored model) | JSON: `{timestamp, session_id, endpoint(route template), provider, model, entities_detected, timing_ms}` — metadata only, never PII/content/fakes (FR-016). |

---

## 8. Configuration

**No configuration change.** All reads use existing `Settings` fields: `openai_api_key`,
`anthropic_api_key` (presence → `key_configured`), `default_model` (resolved `model`),
`redis_session_ttl` (the sliding TTL whose remaining value `GET /v1/sessions` reports). No new env vars.

---

## 9. Reused / frozen (referenced, not modified)

- **Redis schema** `fwd:/rev:/forms:/meta/corefs`, the AES-256-GCM envelope, and the session TTL —
  frozen (Constitution III; regression contract). `SessionMeta` fields are unchanged; this epic only
  starts incrementing the existing `message_count`.
- **Detection/generation** (EPIC 2/3): `DetectionEngine.detect`, `FakeDataGenerator`, inflection,
  fuzzy restore — unchanged.
- **EPIC 5 adapters/router internals** (message conversion, prefix routing, `ollama/` strip, lazy
  client build, no-retry) — unchanged apart from the `CompletionResult` return (§2).
- **EPIC 1 Redis-availability gate** — keeps its gating role; only its plain per-request log line is
  removed (D10/D12).
- **Debug endpoints** `/v1/pseudonymize`, `/v1/depseudonymize`, `/v1/sessions/{id}/mappings`,
  `/v1/detect`, `/health` — unchanged.
