# Contract: `/health` `spacy_model` Readiness Delta (Epic 2)

Epic 2 makes the **`spacy_model`** dependency check in the existing `/health` endpoint **real**. The
endpoint, its always-200 HTTP behaviour, its aggregation rule, and its response **schema are unchanged**
from Epic 1 (`specs/001-infrastructure-runtime/contracts/health.openapi.yaml`). Only the value of
`dependencies.spacy_model` becomes meaningful (FR-028).

## Before (Epic 1)

`check_spacy_model()` was a stub returning `"ok"` unconditionally.

## After (Epic 2)

`check_spacy_model()` returns the real model-readiness state (research D8):

| Model state | `dependencies.spacy_model` | Overall `status` (with Redis ok) |
|---|---|---|
| Loaded & ready | `ok` | `ok` |
| Loading / failed to load | `unavailable` | `degraded` |

- The check is an **O(1) flag read** (`is_model_ready()`), preserving the Epic 1 `/health` < 500 ms
  budget (SC-002) — it never runs an inference.
- `/health` **always returns HTTP 200**, even when `spacy_model` is `unavailable` (Epic 1 FR-022, unchanged).
- Aggregation unchanged: overall `degraded` if **any** dependency (`redis`, `spacy_model`) is
  `unavailable`, else `ok` (Epic 1 FR-024).

## Example (model not yet loaded, Redis ok)

```json
{
  "status": "degraded",
  "dependencies": { "redis": "ok", "spacy_model": "unavailable" }
}
```

## Relationship to `/v1/detect`

The same readiness flag gates detection: while `spacy_model` is `unavailable`, `POST /v1/detect` returns
**503** (FR-030) — the two surfaces report consistently but independently (a `/health` query never
triggers a model load).
