# Research: EPIC 5 — Provider Adapters & Model-Based Router

**Feature**: `specs/006-provider-adapters-router` | **Date**: 2026-06-17

This document resolves the design unknowns for EPIC 5. The stack is fixed (Constitution Technology
Constraints + the provided tech context); no alternatives to Python 3.12 / FastAPI / async clients are
evaluated. Each decision records what was chosen, why, and the alternative rejected. The EPIC 4 provider
port (`LLMProvider`, `ChatMessage`, `LLMProviderError`) and the Ollama/echo adapters are **reused**; the
pipeline and the chat flow are unchanged except for `chat.py`'s error mapping.

---

## D1 — Provider SDKs: official `openai` & `anthropic`, async, **no retry**

**Decision**: Add the official `openai` and `anthropic` Python SDKs to
`apps/gateway-api/pyproject.toml` `[project].dependencies`. Use their **async** clients
(`openai.AsyncOpenAI`, `anthropic.AsyncAnthropic`) so the adapters fit the port's
`async def complete(...)`. Construct every client with **`max_retries=0`** so the SDK does **not**
auto-retry (the spec forbids retries/backoff; both SDKs default to `max_retries=2`). `httpx` stays the
transport for the **reused** Ollama adapter (Ollama has no first-party SDK in scope).

**Rationale**: The official clients give native exception types (connection/timeout/rate-limit/auth/
not-found) that map cleanly to the error taxonomy (D6), and async clients keep the event loop free
during the synchronous round-trip. `max_retries=0` is the single most important non-default — without it
the SDK silently retries a 429, contradicting FR-020.

**Alternatives rejected**:
- *Call the provider HTTP APIs with `httpx` directly* (as Ollama does) — reimplements auth, error
  decoding, and request shaping the SDKs already provide; more surface, no benefit.
- *Sync clients wrapped in a thread* — adds complexity; the SDKs ship async clients.

---

## D2 — `LLMRouter` shape; the **default model is resolved by the endpoint**, not the router

**Decision**: `gateway_api/llm_providers/llm_router.py` defines `LLMRouter(LLMProvider)` (composite).
`complete(messages, *, model)` selects an adapter by the **model prefix** and delegates; `health_check()`
delegates to the **default model's** provider. The router holds a **prefix → adapter-factory** registry
and **lazily builds + caches** each adapter on first use (D8). It receives the configured
`default_model` (for `health_check` only) at construction.

Crucially, the **endpoint keeps EPIC 4's line** `model = request.model or get_settings().default_model`,
so the router always receives a **concrete** model string and `complete`'s signature
(`*, model: str`) — i.e. the **port — is unchanged** (FR-001). "No model → default model" (FR-016) is
satisfied by that unchanged endpoint line plus the new default **value** (D9); the router is pure prefix
dispatch.

**Rationale**: Keeps the port byte-identical (Constitution IV / FR-001), keeps the endpoint change
minimal (only the error map + the swapped factory), and puts all *routing* knowledge (prefixes) inside
the router. The factory registry makes the router trivially testable — tests inject recording doubles
per prefix and assert dispatch + stripping (D12).

**Alternatives rejected**:
- *Router owns the default and `complete` takes `model: str | None`* — would change the port's contract
  (FR-001 says reuse unchanged) and the endpoint's call site for no real gain.
- *Eagerly construct all three adapters in `__init__`* — would build hosted clients (and could touch
  keys) for providers a given deployment never uses; the lazy registry (D8) is the keys-optional-at-
  startup contract.

---

## D3 — Routing rules & the `ollama/` prefix strip (exact)

**Decision**: In `LLMRouter.complete`, route by **prefix only** (no model-name allowlist):

| Model prefix | Adapter | Model sent to the adapter |
|--------------|---------|---------------------------|
| `gpt-` | `OpenAIProvider` | the model **unchanged** (e.g. `gpt-4o`) |
| `claude-` | `AnthropicProvider` | the model **unchanged** (e.g. `claude-3-5-sonnet`) |
| `ollama/` | `OllamaProvider` | the model **with the `ollama/` prefix stripped** (`ollama/qwen2.5:3b` → `qwen2.5:3b`) |
| anything else | — | raise `LLMProviderError(kind="unknown_model", …)` listing `gpt-`, `claude-`, `ollama/` → **400**; nothing is sent to any provider |

The recognized-prefix list lives in **one** place in the router and is interpolated into the
`unknown_model` message so the error always matches the actual routing table.

**Rationale**: Direct from the spec (FR-014/FR-015) and Constitution IX (no registry). Ollama is
**not** a catch-all — an unrecognised model is the caller's mistake, surfaced as 400. Stripping only the
`ollama/` prefix (the only namespaced one) keeps the reused Ollama adapter unchanged: it still receives a
bare Ollama model name exactly as in EPIC 4.

**Alternatives rejected**: *Treat Ollama as the default for unknown models* — explicitly forbidden
(silent provider assumption); *a per-provider model registry* — out of scope.

---

## D4 — OpenAI adapter (native shape, length truncation, errors)

**Decision**: `OpenAIProvider.complete` calls
`await client.chat.completions.create(model=model, messages=[{role, content}, …])` — **no conversion**,
because the OpenAI shape is the system's native shape (a `system` message is passed through as the first
message). It returns `response.choices[0].message.content`. When
`response.choices[0].finish_reason == "length"` it logs a **warning** (`finish_reason` + `model` only —
never content) and **still returns the partial content** (FR-005). A deprecated/unknown model that
slips past prefix routing makes the SDK raise `NotFoundError`, which the adapter surfaces as
`kind="missing_model"` carrying the **provider's own message** (FR-006). Exception mapping in D6. Client
built with `max_retries=0` (D1).

**Rationale**: Matches FR-004/FR-005/FR-006 exactly. Returning partial content on truncation (rather
than failing) is the spec's chosen behaviour; surfacing the SDK's message keeps the "no allowlist,
provider speaks for itself" stance.

**Alternatives rejected**: *Raise on `finish_reason == "length"`* — contradicts FR-005; *pre-validate
model names* — contradicts the no-allowlist decision (D3) and FR-006.

---

## D5 — Anthropic message normalization (exact, per the Messages API)

**Decision**: `AnthropicProvider` converts the OpenAI-shaped `list[ChatMessage]` into Anthropic's
`(system, messages)` contract before
`await client.messages.create(model=model, system=…, messages=…, max_tokens=…)`:

1. **system**: collect the `content` of every message with `role == "system"`, in order; join with
   `"\n\n"`; pass as the top-level `system` parameter. If there are **no** system messages, **omit**
   the parameter entirely (do not pass `system=""`).
2. **messages**: drop the system messages; from the remaining user/assistant turns, **merge any two
   consecutive same-role messages into one** (join `content` with `"\n\n"`) so the history alternates.
   The conversation **begins with a user turn** (the chat endpoint already guarantees the last message
   is a user turn; for normal chat the first non-system turn is a user turn).
3. **max_tokens**: **required** by the API — pass `settings.anthropic_max_tokens` on **every** call
   (D9).
4. `temperature`/`top_p`/etc. are left at SDK defaults (out of scope).

It returns the text content blocks joined into one string
(`"".join(block.text for block in response.content if block.type == "text")`). Client built with
`max_retries=0` (D1).

**Rationale**: Directly implements FR-007–FR-010 and the spec's US3 acceptance scenarios. Concatenating
with `"\n\n"` (the documented Anthropic convention) preserves readability; omitting `system` when empty
avoids sending a meaningless empty system prompt.

**Edge note (documented, Constitution IX)**: A history whose first non-system turn is an *assistant*
turn is atypical for this gateway (clients send user-first; the endpoint enforces a user **last** turn).
The normalization performs the three transforms above and does **not** synthesise or drop a leading
assistant turn; if such an input ever occurs, Anthropic surfaces its own error (mapped via D6) — an
accepted limitation rather than added complexity.

**Alternatives rejected**: *Keep `system` as a message role* — Anthropic rejects it; *send `system=""`
when empty* — wasteful and surprising; *hard-code `max_tokens`* — the spec requires it from config (D9).

---

## D6 — Extended error taxonomy → single `kind → HTTP` map

**Decision**: Extend `base.ProviderErrorKind` to
`Literal["unreachable", "missing_model", "timeout", "rate_limit", "auth", "unknown_model"]` (additive;
the `LLMProvider`/`ChatMessage`/`LLMProviderError` shapes are otherwise unchanged). Keep **one**
`kind → HTTP` map in `api/chat.py`:

| `kind` | HTTP | Raised by |
|--------|------|-----------|
| `unreachable` | **503** | Ollama (existing); OpenAI/Anthropic `APIConnectionError` |
| `missing_model` | **503** | Ollama (existing); OpenAI/Anthropic `NotFoundError` (deprecated/unknown model) |
| `timeout` | **504** | Ollama (existing); OpenAI/Anthropic `APITimeoutError` |
| `rate_limit` | **429** | OpenAI/Anthropic `RateLimitError` (429 upstream) — **no retry** |
| `auth` | **503** | missing key (pre-call check) or SDK `AuthenticationError`/`PermissionDeniedError` — message names the key |
| `unknown_model` | **400** | `LLMRouter` when no prefix matches (before any adapter is called) |

SDK exception → `kind`:

- **OpenAI**: `APIConnectionError → unreachable`; `APITimeoutError → timeout`;
  `RateLimitError → rate_limit`; `AuthenticationError`/`PermissionDeniedError → auth`;
  `NotFoundError → missing_model`. The `LLMProviderError` message carries the SDK's message
  (provider-generated; safe — no user PII).
- **Anthropic**: the analogous `APIConnectionError`/`APITimeoutError`/`RateLimitError`/
  `AuthenticationError`/`NotFoundError` map identically.

Every error response **echoes `session_id`** and a readable `detail` (the EPIC 4 `_error` helper,
unchanged). Replace EPIC 4's inline `status_code = 504 if exc.kind == "timeout" else 503` with a
module-level `_ERROR_STATUS: dict[ProviderErrorKind, int]` lookup.

**Rationale**: FR-019/FR-023 require one centralized mapping. A dict keeps the map exhaustive and
single-sourced; adding a future kind is one row. `rate_limit` and `auth` both arise inside
`complete()` (so they flow through the same `except LLMProviderError` the endpoint already has);
`unknown_model` arises in the router's `complete()` too, so **no new exception type and no second map**
are needed.

**Alternatives rejected**: *A separate `RoutingError`/`HTTPException` for unknown model* — would split
the mapping across two places, contradicting FR-023; reusing `LLMProviderError(kind="unknown_model")`
keeps it in one map.

---

## D7 — Where `unknown_model` (400) is raised, and "nothing is sent to any provider"

**Decision**: The `LLMRouter.complete` raises `LLMProviderError(kind="unknown_model")` **before**
delegating to any adapter, so no provider call is made (FR-015). The chat flow is unchanged: validate
(400 for empty/non-user-last) → `pseudonymize_messages` → `provider.complete` (the router). For an
unknown model the router raises immediately inside `complete`; pseudonymisation may have already run, but
that is **internal, network-free, and leak-free** — "nothing is sent to any provider" still holds. The
endpoint maps the kind to **400** via the D6 table.

**Rationale**: Keeps prefix knowledge solely in the router (Constitution IV — the endpoint stays
provider-agnostic and never inspects model strings). The cost of pseudonymising before discovering a bad
model is negligible (session-scoped, TTL'd, no network) and avoids leaking routing rules into the
handler.

**Alternatives rejected**: *Validate the prefix in the handler before `complete`* — would duplicate the
routing table outside the router and couple the endpoint to provider prefixes.

---

## D8 — Client lifecycle: lazy, cached, **keys optional at startup**

**Decision**: Provider API keys stay optional to **start** the process (unchanged config contract). The
router lazily builds + caches each adapter on first use; each hosted adapter lazily builds + caches its
SDK client **only when its key is present**:

- `OpenAIProvider`/`AnthropicProvider` are constructed with the key (`settings.openai_api_key` /
  `settings.anthropic_api_key`, possibly `None`) + (for Anthropic) `anthropic_max_tokens`. The SDK
  client is created **on first `complete()`** and cached on the instance.
- If the key is **missing** (`None`/blank) at first `complete()`, the adapter raises
  `LLMProviderError(kind="auth", "OPENAI_API_KEY is not configured")` (naming the key, **never** a
  value) → **503**. No SDK client is constructed.
- An **invalid** key reaches the SDK, which raises `AuthenticationError` → `kind="auth"` → **503**
  (message names the key).

`get_llm_provider()` keeps its `@lru_cache`, so the router (and its cached adapters/clients) is a
process singleton → connection pooling for free.

**Rationale**: Implements FR-021/FR-022 and the tech-context lifecycle note exactly: build once, cache,
lazily, only when the key exists; the missing-key error is a **request-time** 503 that names the key, not
a startup failure. Singleton router + per-instance client cache gives pooled connections without globals.

**Alternatives rejected**: *Validate keys at startup* — breaks "optional at startup" and the keyless
offline demo; *new client per request* — drops connection pooling and is slower.

---

## D9 — Configuration delta

**Decision** (`config.py` + `.env.example`):

| Setting | Env var | EPIC 4 | EPIC 5 | Note |
|---------|---------|--------|--------|------|
| `default_llm_provider` | `DEFAULT_LLM_PROVIDER` | `"openai"` | **REMOVED** | Single source of truth for provider selection is now the model prefix; the setting was never consulted for routing. |
| `default_model` | `DEFAULT_MODEL` | `"gpt-4o"` | **`"ollama/qwen2.5:3b"`** | Keyless, offline demo path (FR-017): the no-model default routes to local Ollama. |
| `anthropic_max_tokens` | `ANTHROPIC_MAX_TOKENS` | — | **NEW** `4096` | Required on every Anthropic call (FR-010 / D5). |
| `openai_api_key` | `OPENAI_API_KEY` | exists | unchanged | Optional at startup; auth error on first use (D8). |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | exists | unchanged | Optional at startup; auth error on first use (D8). |
| `ollama_base_url` | `OLLAMA_BASE_URL` | exists | unchanged | The reused Ollama adapter's endpoint. |
| `ollama_timeout` | `OLLAMA_TIMEOUT` | exists | unchanged | The separately-configurable long timeout for slow local models (FR-012). |

Removing `default_llm_provider` requires updating **`main.py`**'s startup log line (it currently logs
`settings.default_llm_provider`); the log keeps `model` (+ `redis_configured`, `session_ttl`) and drops
the `provider=` field. `.env.example` drops `DEFAULT_LLM_PROVIDER`, sets
`DEFAULT_MODEL=ollama/qwen2.5:3b`, adds `ANTHROPIC_MAX_TOKENS=4096`, and refreshes the now-stale EPIC 4
comments.

**Rationale**: FR-016/FR-017 + the tech context. One default (`default_model`) drives both the no-model
path and (via prefix) the provider. The Ollama default keeps the keyless demo working out of the box.

**Alternatives rejected**: *Keep `default_llm_provider` for back-compat* — dead config that contradicts
"single source of truth is the model" and risks confusion.

---

## D10 — `get_llm_provider()` wiring & test override

**Decision**: `get_llm_provider()` (in `llm_providers/__init__.py`) now builds and returns the
`LLMRouter` with the real per-prefix adapter factories (OpenAI/Anthropic from keys, Ollama from
`ollama_base_url`/`ollama_timeout`) and `settings.default_model`, replacing the hardcoded
`OllamaProvider`. It keeps `@lru_cache` (D8). Tests continue to **override the FastAPI dependency**
`get_llm_provider` with a stub/echo/recording provider, so endpoint tests bypass the router entirely
(the EPIC 4 `test_chat_api` override pattern is unchanged); router behaviour is tested directly in
`test_llm_router.py` with injected recording adapters.

**Rationale**: FR-018 — the router *becomes* what the factory returns, with no pipeline/endpoint change.
Because chat tests override the dependency, the existing EPIC 4 chat suite stays green untouched.

---

## D11 — Doc / Postman / compose alignment & the regression contract

**Decision**:
- **Regression contract frozen**: EPIC 2/3/4 public behaviour, the Redis `fwd:/rev:/forms:/meta` layout,
  and the AES-256-GCM envelope are **unchanged**. The Ollama adapter and the EPIC 4 pipeline/chat flow
  are untouched apart from `chat.py`'s centralized error map + `unknown_model` branch. The EPIC 4 chat
  round-trip now flows **through the router**, and the default `ollama/qwen2.5:3b` routes to the existing
  Ollama adapter (stripped to `qwen2.5:3b`); echo/stub tests are unaffected because they override
  `get_llm_provider` directly.
- **Because Ollama now requires the `ollama/` prefix**, update the **Postman** collection's "Chat" folder
  example models and the **`dev/ollama/README.md`** / **`.claude/rules/local-llm-ollama.md`** smoke-test
  examples to use prefixed names (`ollama/qwen2.5:3b`). A bare `qwen2.5:3b` would now 400 (unknown model).
- **docker-compose**: the `gateway-api` service **already** declares
  `extra_hosts: ["host.docker.internal:host-gateway"]` (present in the repo). **No change** — verify
  only; the `.env.example` note that flags it is retained.

**Rationale**: Routing-by-prefix is a behavioural change for the one externally-documented model name
(the Ollama smoke test), so the docs/Postman must move to prefixed names or they will 400. Everything
else is frozen by the regression contract.

**Alternatives rejected**: *Accept bare Ollama names too (implicit `ollama/`)* — reintroduces the silent
catch-all the spec forbids (FR-015).

---

## D12 — Testing strategy (network-free; no real keys)

**Decision**: All new tests run offline by **mocking the SDK async clients** (no network, no keys):

- **Router** (`tests/llm_providers/test_llm_router.py`): inject recording adapters per prefix; assert
  `gpt-*` → OpenAI, `claude-*` → Anthropic, `ollama/*` → Ollama with the name **stripped**
  (`ollama/qwen2.5:3b` → adapter sees `qwen2.5:3b`); an unrecognised model raises
  `kind="unknown_model"`; an adapter raising `kind="auth"` (missing key) propagates; `health_check`
  delegates to the default model's provider.
- **OpenAI adapter** (`test_openai_provider.py`): pass-through (no conversion; system stays first);
  `finish_reason == "length"` logs a warning (assert via `caplog`) **and** returns the partial content;
  each SDK exception (`APIConnectionError`/`APITimeoutError`/`RateLimitError`/`AuthenticationError`/
  `NotFoundError`) maps to the right `kind`; **no retry** (the create mock is called exactly once);
  a missing key raises `kind="auth"` without building a client.
- **Anthropic adapter** (`test_anthropic_provider.py`): system messages lifted + concatenated into the
  `system` param; the no-system case omits `system`; consecutive same-role merged so the history
  alternates user-first; `max_tokens` passed from config; exceptions map per D6; no retry.
- **Endpoint** (`tests/test_chat_api.py`, extended): a provider raising `kind="rate_limit"` → **429**;
  `kind="auth"` → **503** (detail names the key); an `unknown_model` model → **400**; each **preserves
  `session_id`**. The EPIC 4 **no-PII** assertions (no original in the provider payload captured by the
  recording provider, none in `caplog`) still hold for the routed path.

The SDKs are mocked by patching the adapter's client-builder (or the `AsyncOpenAI`/`AsyncAnthropic`
symbols) with an `AsyncMock`; `pytest-asyncio` is `asyncio_mode = "auto"` and `fakeredis` is already a
dev dependency, so the store-backed endpoint tests run offline.

**Rationale**: Satisfies FR-027/SC-009 — every behaviour is covered by network-free tests. Mocking the
SDK client (not the network) keeps tests fast and key-free while still exercising the real
exception-to-`kind` mapping and the no-retry guarantee.

**Alternatives rejected**: *Hit real provider sandboxes in CI* — needs keys + network, violates
FR-027; *record/replay HTTP fixtures* — heavier than mocking the SDK's typed exceptions.
