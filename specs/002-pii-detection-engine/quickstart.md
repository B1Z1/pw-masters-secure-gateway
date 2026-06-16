# Quickstart & Validation: EPIC 2 — PII Detection Engine

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

A run/validation guide proving the detection engine works end to end. Implementation details live in
`tasks.md` (after `/speckit-tasks`) and the source; this file is how a reviewer checks it. All commands
run from the repo root unless noted.

## Prerequisites

- Epic 1 stack working (`apps/gateway-api` runs; `GET /health` returns 200).
- New deps installed: `presidio-analyzer`, `pyyaml` (added to `apps/gateway-api/pyproject.toml`).
  ```bash
  nx run gateway-api:install        # or: (cd apps/gateway-api && uv sync)
  ```
- **Polish model** present for native dev (already baked into the container image):
  ```bash
  (cd apps/gateway-api && uv run python -m spacy download pl_core_news_lg)
  ```

## Run the unit tests (no model required for recognizer/checksum tests)

```bash
nx run gateway-api:test           # → uv run pytest tests/
```

Expected: all `tests/detection/*` pass — checksums (PESEL/NIP/REGON/mod-97), each recognizer
(positive / negative / edge), scoring bands, threshold post-filter, and the engine overlap/offset tests.
Engine/API tests that need the model skip automatically if `pl_core_news_lg` is absent.

## Start the backend (native dev)

```bash
nx run gateway-api:serve          # uvicorn --reload on :8000
```

The model loads in the background at startup; `/health` reports `spacy_model: unavailable` →
`ok` once loaded (a few seconds).

---

## Validation scenarios

Map to the spec's user stories and success criteria. Use the debug endpoint
([contracts/detect.openapi.yaml](contracts/detect.openapi.yaml)).

### V1 — Detect & inspect (US1, SC-001/SC-002/SC-010)

```bash
curl -s localhost:8000/v1/detect -H 'content-type: application/json' \
  -d '{"text":"Jan Kowalski, e-mail jan@example.pl, tel. +48 601 234 567, dnia 12 stycznia 2024 r."}' | jq
```

Expect entities for `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `DATE_TIME`, each with `start/end/score/
text/metadata`. For every entity, `text == input[start:end]` (SC-002). Empty input → `{"entities": []}`
(SC-010):

```bash
curl -s localhost:8000/v1/detect -H 'content-type: application/json' -d '{"text":""}' | jq
```

### V2 — Validated identifiers + metadata (US2, SC-003/SC-004/SC-009)

```bash
curl -s localhost:8000/v1/detect -H 'content-type: application/json' \
  -d '{"text":"PESEL: 44051401359, NIP 0000000000? konto PL61109010140000071219812874"}' | jq
```

Expect: `PESEL` with `metadata.gender`, `metadata.birth_date`, `checksum_valid: true`, high score (≈0.99
labelled); `NIP` accepted with leading zeros (FR-009); `POLISH_BANK_ACCOUNT` with `format: IBAN`. Then
flip a digit to break a checksum and confirm the entity **still appears** at a low score (~0.30, SC-004),
not dropped.

### V3 — Scoring & thresholds (US3, SC-005/SC-006/SC-007)

- **Deterministic**: run V2 twice → identical entities and scores (SC-005).
- **Paranoid / disable**: edit `apps/gateway-api/gateway_api/detection/default_thresholds.yaml` (or the
  file at `DETECTION_THRESHOLDS_PATH`): set `PESEL: 0.0` → every candidate surfaces; set `PESEL: 1.0` →
  no PESEL returned (SC-006). Re-run the curl **without restarting** the server → change is live (SC-007).
- **Context**: same identifier with vs. without a nearby label → labelled scores higher (FR-017).

### V4 — Overlap resolution (US4, SC-008)

```bash
# 14-digit REGON whose first 9 are a valid REGON-9 → ONE 14-digit entity
curl -s localhost:8000/v1/detect -H 'content-type: application/json' \
  -d '{"text":"REGON 12345678512347"}' | jq
# Address containing a city → no separate LOCATION inside the address span
curl -s localhost:8000/v1/detect -H 'content-type: application/json' \
  -d '{"text":"Adres: ul. Kowalskiego 12/3, 00-950 Warszawa"}' | jq
```

Expect a single containing entity per region; `ul. Kowalskiego` is part of the address, not a PERSON
(FR-025); the city is subsumed (FR-024).

### V5 — Health readiness & gating (US5, FR-028/FR-030/FR-031)

- `GET /health` → `dependencies.spacy_model` is `ok` once loaded; `degraded` if the model failed to load
  ([contracts/health-readiness.md](contracts/health-readiness.md)).
- **Model down** → `POST /v1/detect` returns **503** (no partial results, FR-030). Reproduce in tests by
  forcing `is_model_ready()` false.
- **Redis down** → `POST /v1/detect` **still serves** (Redis-gate exempt, FR-031), while other non-health
  routes 503 as in Epic 1.

### V6 — No PII in logs (Constitution VIII)

Run any detect call and inspect server logs: only entity **types/counts/scores/timings** appear — never
the input text or matched values.

---

## Known limitations (Constitution IX)

See [research.md](research.md) "Known limitations": worded-date coverage gaps, `pl_core_news_lg`
weakness on rare/foreign or inflected names, and intentional over-detection (recall over precision).
Formal P/R/F1 evaluation is Epic 8 (out of scope here).
