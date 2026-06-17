# Implementation Plan: EPIC 4 — Anonymization Pipeline & First End-to-End LLM Round-Trip

**Branch**: `im/04-pseudonimization-pipeline` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-anonymization-pipeline/spec.md`

## Summary

Tie the existing detection (EPIC 2) and substitution + reversible store (EPIC 3) into one reusable
`AnonymizationPipeline`, add the missing prefix-anchored fuzzy fallback to the outbound restore path
(PERSON/LOCATION only), put one real LLM (local Ollama) behind an abstract provider port with a
network-free echo double, and expose a minimal OpenAI-shaped `POST /v1/chat/completions` that runs
inbound → LLM → outbound. The whole messages array is pseudonymised every turn so no original ever
reaches the LLM; the answer is de-pseudonymised before return. EPIC 3 behaviour, the Redis field
layout, and the AES-256-GCM envelope are frozen — the inbound substitution logic is **extracted** from
`api/pseudonymize.py` into the pipeline (not duplicated), and `MappingStore.restore_text` gains an
additive `fuzzy=False` flag so the existing path is byte-identical. Technical approach and parameters
are fixed in [research.md](./research.md) (D1–D10); component shapes in [data-model.md](./data-model.md)
and [contracts/](./contracts/).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, `httpx` (async, already present — Ollama REST), `pydantic` /
`pydantic-settings`, `redis.asyncio`; reused: Presidio + spaCy `pl_core_news_lg` (detection), Faker
`pl_PL` + custom checksum generators (substitution), `cryptography` (AES-256-GCM). **No new heavy
dependency**; bounded Levenshtein already exists in-repo.

**Storage**: Redis 7 — reused EPIC 3 session store; `fwd:/rev:/forms:/meta` field layout and the
AES-256-GCM envelope are **frozen** (no new keys/fields).

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), `fakeredis`; echo/stub provider
keeps the suite network-free.

**Target Platform**: Linux server via Docker Compose (network `pw-masters-secure-gateway`); also native
via `uv` (`apps/gateway-api`, package `gateway_api`) in the Nx monorepo.

**Project Type**: Web service (backend `apps/gateway-api`).

**Performance Goals**: None defined (Constitution V — synchronous; end-to-end latency is dominated by
the LLM and not an SLA for this epic).

**Constraints**: No original PII in logs or in any outgoing LLM request (Constitution I/VIII);
synchronous only, no streaming (Constitution V); bounded `OLLAMA_TIMEOUT`; EPIC 3 regression contract
(public behaviour + Redis/encryption wire formats) unchanged.

**Scale/Scope**: Master's-thesis prototype; one provider (Ollama) + one stub; multi-turn Polish
civil-law conversations; trusted/dev exposure (auth out of scope).

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Status | How this plan complies |
|-----------|--------|------------------------|
| I. Privacy by Design | PASS | Inbound pseudonymises **every** message each turn before the single `provider.complete`; there is no passthrough path. No-leak invariant asserted in tests (D10). |
| II. Recall over Precision | PASS | Detection reused unchanged (`get_engine()`); no threshold changes. |
| III. Reversibility within Session | PASS | EPIC 3 store reused; AES-256-GCM, TTL, key handling unchanged; `restore_text` change is additive (`fuzzy=False` default). |
| IV. Provider Agnosticism | PASS | Pipeline/endpoint depend only on the `LLMProvider` port; Ollama is one adapter; a new provider needs no pipeline change. |
| V. Synchronous Only | PASS | Ollama called with `stream=false`; outbound runs on the complete answer; SSE explicitly out of scope. |
| VI. Polish First | PASS | Reuses Polish detection/generation/inflection; the fuzzy anchor is tuned to Polish suffix inflection (stem-prefix overlap). |
| VII. Realistic Substitution | PASS | Reuses EPIC 3 realistic fakes; no abstract placeholders introduced. |
| VIII. No PII in Logs | PASS | Chat/pipeline log `session_id`, types/counts, timings only; tests assert no original in provider payload or `caplog`. |
| IX. Simplicity over Completeness | PASS | Fuzzy hit restores **base/nominative** form (documented limitation); one provider only; minimal response shape — richer behaviour deferred. |

**Result**: PASS, no violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-anonymization-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1–D10 (fuzzy params, provider, errors, extraction)
├── data-model.md        # Phase 1 — transport models + component contracts
├── quickstart.md        # Phase 1 — offline + live validation guide
├── contracts/
│   ├── chat-endpoint.md
│   ├── llm-provider-port.md
│   └── anonymization-pipeline.md
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
apps/gateway-api/gateway_api/
├── pipeline/                         # NEW
│   ├── __init__.py
│   └── anonymization_pipeline.py     # orchestrator: pseudonymize_text/_messages, depseudonymize_text
├── llm_providers/                    # NEW
│   ├── __init__.py
│   ├── base.py                       # LLMProvider (abstract), ChatMessage, LLMProviderError(kind=…)
│   ├── ollama_provider.py            # POST {OLLAMA_BASE_URL}/api/chat, stream=false, error mapping
│   └── echo_provider.py             # deterministic, network-free test double
├── pseudonym_vault/
│   ├── fuzzy_restoration.py          # NEW — FuzzyNameRestorer (prefix-anchored, PERSON/LOCATION)
│   └── mapping_store.py              # CHANGED — restore_text(…, fuzzy: bool = False) additive
├── api/
│   ├── chat.py                       # NEW — POST /v1/chat/completions (happy path + 400/503/504)
│   └── pseudonymize.py               # CHANGED — delegate inbound to pipeline (behaviour preserved)
├── config.py                         # CHANGED — add ollama_timeout (OLLAMA_TIMEOUT)
└── main.py                           # CHANGED — include chat_router (NOT gate-exempt)

apps/gateway-api/tests/
├── test_chat_api.py                          # NEW — happy path + 400/503/504, session_id preserved, no-PII
├── pipeline/test_anonymization_pipeline.py   # NEW — round-trip via EchoProvider, multi-turn determinism
├── pseudonym_vault/test_fuzzy_restoration.py # NEW — fuzzy positive/negative, exact-only, tie-skip
└── llm_providers/test_ollama_provider.py     # NEW — error→kind mapping (mocked httpx, no network)
```

Optional deployment add-on (NOT part of the core stack — research D11):

```text
dev/ollama/                              # NEW — opt-in self-hosted LLM for dev/demo
├── docker-compose.ollama.yml           # in-network `ollama` service + OLLAMA_BASE_URL override
├── pull-model.sh                       # pull DEFAULT_MODEL into the container
└── README.md                           # how to run; macOS CPU-only / Linux GPU caveats
```

**Structure Decision**: Backend-only change within the existing `apps/gateway-api` package, following
the EPIC 3 by-domain layout and the active naming rule (`.claude/rules/python-naming-conventions.md`):
role-revealing module names (`anonymization_pipeline.py`, `ollama_provider.py`,
`fuzzy_restoration.py`), no generic names. New top-level packages `pipeline/` and `llm_providers/`
mirror the existing `pii_detection/` / `pseudonym_vault/` / `pseudonym_generation/` decomposition. The
two EPIC 3 touch-points (`pseudonymize.py` delegation, `restore_text` additive flag) are constrained by
the regression contract. The LLM backend itself is **not** owned by the core stack (Constitution IV):
the gateway connects out via `OLLAMA_BASE_URL` (or, later, hosted-API keys), and a self-hosted Ollama is
an **opt-in** compose add-on under `dev/ollama/` rather than a service in the core `docker-compose.yml`
(research D11).

## Complexity Tracking

No constitution violations — section intentionally empty.

## Phase notes

- **Phase 0 (research.md)**: all unknowns resolved — fuzzy placement (D1), candidate-set = stored
  forms (D2), frozen fuzzy parameters incl. the `{PERSON, LOCATION}` allowlist and real label mapping
  (D3), token alignment (D4), provider port + error taxonomy + Ollama adapter (D5–D7), inbound
  extraction (D8), endpoint + Redis gate (D9), offline test strategy (D10). No `NEEDS CLARIFICATION`
  remain.
- **Phase 1 (data-model.md, contracts/, quickstart.md)**: transport + component models defined;
  chat-endpoint, provider-port, and pipeline contracts written; validation guide covers offline
  (echo/stub) and live (Ollama) runs and the EPIC 3 regression checks.
- **Phase 2**: `/speckit-tasks` will derive the dependency-ordered task list (suggested spine:
  config delta → provider port + echo → Ollama adapter → fuzzy_restoration + restore_text flag →
  pipeline → pseudonymize.py extraction → chat endpoint + main wiring → tests at each layer).
