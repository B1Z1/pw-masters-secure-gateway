# Contract: Provider-Error Taxonomy (centralized `kind → HTTP`)

**Feature**: EPIC 5 | `gateway_api/llm_providers/base.py` (the `kind` enum) + `gateway_api/api/chat.py`
(the single map). Extends EPIC 4's taxonomy; the mapping stays in **one** place (FR-019/FR-023).

## `ProviderErrorKind` (extended in `base.py`)

```text
Literal["unreachable", "missing_model", "timeout", "rate_limit", "auth", "unknown_model"]
```

The last three are **new**; the additions are backward-compatible (existing adapters/handler unaffected).

## Single map (in `api/chat.py`)

| `kind` | HTTP | Meaning / source | Retry? |
|--------|------|------------------|--------|
| `unreachable` | **503** | provider connection failed | no |
| `missing_model` | **503** | model not found (Ollama 404 / SDK `NotFoundError`, incl. deprecated models) | no |
| `timeout` | **504** | call exceeded the timeout (Ollama `OLLAMA_TIMEOUT` / SDK `APITimeoutError`) | no |
| `rate_limit` | **429** | upstream 429 (SDK `RateLimitError`) | **no** (FR-020) |
| `auth` | **503** | missing or invalid API key — message **names** the key (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), never a value | no |
| `unknown_model` | **400** | router found no matching prefix — message lists `gpt-`, `claude-`, `ollama/`; nothing sent to any provider | n/a |

Implementation: `_ERROR_STATUS: dict[ProviderErrorKind, int]` replaces EPIC 4's inline
`status_code = 504 if exc.kind == "timeout" else 503`; the handler does `status = _ERROR_STATUS.get(exc.kind, 503)`.

## Invariants

- **Every** error response preserves `session_id` and a readable `detail` (EPIC 4 `_error` helper).
- **No retry anywhere**: adapters build SDK clients with `max_retries=0`; the rate-limit error is
  surfaced to the client unchanged (FR-020).
- **Keys optional at startup**: `auth` is a **request-time** error on first use of a provider that needs
  a key — startup with no keys succeeds (FR-022).
- **No PII in error paths**: messages/logs carry `session_id`, `kind`, model, counts, status only —
  never message content, originals, fakes, or key values (Constitution VIII).

## Acceptance assertions (map to spec)

- `rate_limit` → 429, no retry, `session_id` preserved (SC-006, FR-020).
- `auth` → 503 naming the missing key; startup with no keys succeeds (SC-006, FR-021/FR-022).
- `unknown_model` → 400 listing prefixes, nothing sent (SC-002, FR-015).
- The full `kind → HTTP` decision is single-sourced (FR-023).
