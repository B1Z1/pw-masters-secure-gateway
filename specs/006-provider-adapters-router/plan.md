# Implementation Plan: EPIC 5 — Provider Adapters (Provider-Agnostic) & a Model-Based Router

**Branch**: `006-provider-adapters-router` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-provider-adapters-router/spec.md`

## Summary

Generalize EPIC 4's single-provider slice into a real provider-agnostic layer. Add an **OpenAI
adapter** and an **Anthropic adapter** behind the EPIC 4 `LLMProvider` port (reused **unchanged**),
keep the **Ollama adapter** but select it **explicitly** by an `ollama/` prefix (stripped before
send), and introduce an **`LLMRouter`** — itself an `LLMProvider` (composite) — that dispatches each
request to one adapter by **model prefix**. `get_llm_provider()` now returns the router, replacing the
hardcoded `OllamaProvider`; the pipeline and the chat endpoint do not change. The provider-error
taxonomy is **extended and kept centralized**: `ProviderErrorKind` gains `rate_limit`, `auth`, and
`unknown_model`, and `api/chat.py` holds the single `kind → HTTP` map (unreachable/missing_model → 503,
timeout → 504, rate_limit → 429, auth → 503, unknown_model → 400). API keys stay optional at startup;
the auth error appears only on first use of a provider that needs a key and **names which key** is
missing. Adapters **never retry** (SDK clients built with `max_retries=0`). The EPIC 2/3/4 public
behaviour, the Redis field layout, and the AES-256-GCM envelope are **frozen**. Decisions are fixed in
[research.md](./research.md) (D1–D12); component shapes in [data-model.md](./data-model.md) and
[contracts/](./contracts/).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, `pydantic` / `pydantic-settings`, `redis.asyncio`; **new**: the
official `openai` and `anthropic` Python SDKs (their **async** clients, `max_retries=0`); `httpx`
(unchanged transport for the reused Ollama adapter — no SDK there). Reused: Presidio + spaCy
`pl_core_news_lg`, Faker `pl_PL`, `cryptography` (all via the frozen EPIC 2/3/4 layers). No other new
heavy dependency.

**Storage**: Redis 7 — reused EPIC 3 session store; `fwd:/rev:/forms:/meta` layout and the
AES-256-GCM envelope are **frozen** (no new keys/fields; this epic adds no persisted data).

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), `fakeredis`; the OpenAI/Anthropic
async clients are **mocked** (no real keys, no network); the reused `EchoProvider` keeps pipeline/chat
round-trip tests network-free.

**Target Platform**: Linux server via Docker Compose (network `pw-masters-secure-gateway`); also native
via `uv` (`apps/gateway-api`, package `gateway_api`) in the Nx monorepo.

**Project Type**: Web service (backend `apps/gateway-api`).

**Performance Goals**: None defined (Constitution V — synchronous; end-to-end latency is dominated by
the upstream provider and is not an SLA for this epic).

**Constraints**: No original PII in logs or in any outgoing provider request, **for every provider**
(Constitution I/VIII); synchronous only — no streaming (Constitution V); adapters never retry
(no backoff); routing by prefix only (no model-name allowlist); keys optional at startup; the EPIC 2/3/4
regression contract (public behaviour + Redis/encryption wire formats) is unchanged.

**Scale/Scope**: Master's-thesis prototype; three providers (OpenAI, Anthropic, Ollama) behind one
router + the echo test double; multi-turn Polish civil-law conversations; trusted/dev exposure
(auth out of scope).

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy by Design | PASS | The pipeline is unchanged: every message is pseudonymised before the single `provider.complete`. The router and all three adapters receive **only** the already-pseudonymised array; no passthrough exists. No-leak asserted for the routed path (D12). |
| II. Recall over Precision | PASS | Detection reused unchanged; no threshold changes. |
| III. Reversibility within Session | PASS | EPIC 3 store untouched; AES-256-GCM, TTL, key handling unchanged; no new persisted data. |
| IV. Provider Agnosticism | PASS | **The epic's core.** Pipeline/endpoint depend only on the `LLMProvider` port (reused unchanged); OpenAI/Anthropic/Ollama are interchangeable adapters; the `LLMRouter` is itself the port. Adding/swapping a provider is an adapter + config change only. |
| V. Synchronous Only | PASS | Every adapter calls its provider non-streaming (no `stream=True`); the full answer is returned before de-pseudonymisation; SSE explicitly out of scope. |
| VI. Polish First | PASS | Detection/generation/inflection reused unchanged; the providers are language-agnostic transport — Polish handling is upstream of them. |
| VII. Realistic Substitution | PASS | Reuses EPIC 3 realistic fakes; no placeholders introduced. |
| VIII. No PII in Logs | PASS | Adapters/router/endpoint log only `session_id`, model, counts, status, error `kind` — never message content, originals, or fakes. The truncation **warning logs the finish reason + model only**, never content. The auth error names the **key variable** (`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`), never any secret value. Asserted via `caplog` + captured provider payloads (D12). |
| IX. Simplicity over Completeness | PASS | Prefix routing (no model-name registry); no retries/backoff; minimal text-only response retained; Anthropic conversion is the only transform. Richer behaviour (streaming, full response contract, `/health`) explicitly deferred. |

**Result**: PASS, no violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-provider-adapters-router/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1–D12 (SDKs, router, conversion, taxonomy, config)
├── data-model.md        # Phase 1 — transport/config models + component contracts
├── quickstart.md        # Phase 1 — offline + live validation guide
├── contracts/
│   ├── llm-router.md
│   ├── openai-adapter.md
│   ├── anthropic-adapter.md
│   └── error-taxonomy.md
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
apps/gateway-api/gateway_api/
├── llm_providers/
│   ├── __init__.py                 # CHANGED — get_llm_provider() builds & returns LLMRouter (was OllamaProvider)
│   ├── base.py                     # CHANGED — ProviderErrorKind += "rate_limit", "auth", "unknown_model" (port itself unchanged)
│   ├── ollama_provider.py          # REUSED unchanged — now reached only via the router's "ollama/" branch
│   ├── echo_provider.py            # REUSED unchanged — pipeline/chat test double
│   ├── openai_provider.py          # NEW — OpenAIProvider(LLMProvider) over the async OpenAI client
│   ├── anthropic_provider.py       # NEW — AnthropicProvider(LLMProvider) over the async Anthropic client
│   └── llm_router.py               # NEW — LLMRouter(LLMProvider): prefix dispatch + "ollama/" strip
├── api/
│   └── chat.py                     # CHANGED — central kind→HTTP map (+429/+503/+400); unknown_model→400; session_id preserved
├── config.py                       # CHANGED — drop default_llm_provider; default_model="ollama/qwen2.5:3b"; add anthropic_max_tokens
└── main.py                         # CHANGED — startup log no longer references default_llm_provider

apps/gateway-api/tests/
├── llm_providers/
│   ├── test_openai_provider.py     # NEW — pass-through, length-warning+partial, exception→kind, no retry
│   ├── test_anthropic_provider.py  # NEW — system lift/concat, alternation/merge, max_tokens, exception→kind
│   ├── test_llm_router.py          # NEW — prefix routing, "ollama/" strip, default model, unknown→400, missing key→auth
│   └── test_ollama_provider.py     # REUSED unchanged
└── test_chat_api.py                # CHANGED — add rate_limit→429, auth→503, unknown_model→400 (session_id preserved); EPIC 4 no-PII still holds

apps/gateway-api/pyproject.toml     # CHANGED — add `openai`, `anthropic` to [project].dependencies

Repo root / docs (no behaviour, doc + config alignment):
├── .env.example                    # CHANGED — drop DEFAULT_LLM_PROVIDER; DEFAULT_MODEL=ollama/qwen2.5:3b; add ANTHROPIC_MAX_TOKENS
├── docker-compose.yml              # VERIFY — gateway-api already has extra_hosts host.docker.internal (no-op; confirm only)
├── postman/PW Masters — Secure Gateway API.postman_collection.json   # CHANGED — "Chat" folder uses prefixed model names
├── .claude/rules/local-llm-ollama.md                                  # CHANGED — chat examples use ollama/ prefix
└── dev/ollama/README.md                                               # CHANGED — chat examples use ollama/ prefix
```

**Structure Decision**: Backend-only change inside the existing `apps/gateway-api/gateway_api/llm_providers/`
package, following the EPIC 4 by-domain layout and the active naming rule
(`.claude/rules/python-naming-conventions.md`): role-revealing module names that mirror the dominant
class — `openai_provider.py` (`OpenAIProvider`), `anthropic_provider.py` (`AnthropicProvider`),
`llm_router.py` (`LLMRouter`). No generic names. The provider **port** (`base.py`'s `LLMProvider`,
`ChatMessage`, `LLMProviderError`) is reused unchanged except for **adding** members to the
`ProviderErrorKind` literal — an additive change that does not alter the interface or any existing
adapter. The Ollama adapter and the EPIC 4 pipeline/chat flow are untouched apart from `chat.py`'s
centralized `kind → HTTP` map and the new `unknown_model → 400` branch. The model backend remains a
configuration concern (Constitution IV): no provider is owned by the core stack.

## Complexity Tracking

No constitution violations — section intentionally empty.

## Phase notes

- **Phase 0 (research.md)**: all unknowns resolved — SDK choice + async + no-retry (D1), router shape &
  where the default model is resolved (D2), `ollama/` stripping (D3), OpenAI adapter behaviours
  incl. length-truncation (D4), Anthropic message normalization (D5), extended error taxonomy + single
  map + where `unknown_model` is raised (D6–D7), lazy/cached client lifecycle & missing-key handling
  (D8), config delta incl. the removed default-provider setting (D9), `get_llm_provider`/router wiring
  (D10), doc/Postman/compose alignment & regression contract (D11), offline test strategy (D12). No
  `NEEDS CLARIFICATION` remain.
- **Phase 1 (data-model.md, contracts/, quickstart.md)**: transport/config/component models defined;
  router, OpenAI-adapter, Anthropic-adapter, and error-taxonomy contracts written; validation guide
  covers offline (mocked SDKs + echo) and live (real keys / local Ollama) runs and the EPIC 2/3/4
  regression checks. `CLAUDE.md` plan pointer updated to this plan.
- **Phase 2**: `/speckit-tasks` will derive the dependency-ordered task list (suggested spine:
  deps + config delta → `base.py` kind extension → OpenAI adapter → Anthropic adapter → `LLMRouter`
  → `get_llm_provider` wiring → `chat.py` central map + `unknown_model` 400 → main.py log fix →
  tests at each layer → doc/Postman/compose alignment).
