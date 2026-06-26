# Quickstart: Gateway PII Evaluation Harness

**Feature**: `specs/008-gateway-eval-harness` | **Date**: 2026-06-25

How to build the corpus and run the two-stage evaluation. Two modes: **offline against the live stack**
(the real thesis run) and **in-process** (CI / fast smoke test). Everything is offline — no contract text
leaves the machine (D6).

> See [contracts/cli.md](./contracts/cli.md) for all flags, [contracts/consumed-endpoints.md](./contracts/consumed-endpoints.md)
> for the gateway surface, and [data-model.md](./data-model.md) for result schemas. Implementation lands in
> `tasks.md` / the implementation phase — this guide is for validation, not code.

## Prerequisites

- The Nx monorepo with `uv` and `@nxlv/python` (as `apps/gateway-api` already uses).
- `apps/gateway-eval` installed with its own deps + the path dep on `gateway-api`:
  `nx run gateway-eval:install` (or `uv sync` in `apps/gateway-eval`).
- The spaCy model `pl_core_news_lg` available to the gateway (see the project memory note on native
  install) for any run that hits `/v1/detect` or `/v1/chat/completions`.

## 0. Enable the `echo/` route (one-time, gateway side)

Add the additive `echo/` factory to `get_llm_provider` (see
[contracts/gateway-echo-route.md](./contracts/gateway-echo-route.md)). If the gateway runs from the **baked
docker image**, rebuild it so the new route is present:

```bash
CA_CERT_FILE=~/.certs/netskope-ca.pem docker compose build gateway-api
docker compose up -d redis gateway-api
```

(Native dev: `nx run gateway-api:serve` picks up the change with `--reload`.)

## 1. Build the synthetic corpus (offline, seeded)

```bash
nx run gateway-eval:build-corpus            # default --seed 42 → corpus/data/synthetic/
```
**Expected**: a committed set of synthetic gold JSONL documents; re-running with the same seed produces
byte-identical files. Validate the offset/text invariant holds (it is enforced on write).

## 2. (Optional) Add real contracts — local only

Place manually-annotated real documents under `apps/gateway-eval/gateway_eval/corpus/data/real/` (this
path is **git-ignored**). Each line must conform to [contracts/gold-standard.md](./contracts/gold-standard.md);
the real loader rejects bad offsets. These files are never committed and never published.

## 3. Run Stage 1 against the live stack (no LLM)

```bash
nx run gateway-eval:evaluate -- --stage 1 --base-url http://localhost:8000
```
**Expected**:
- A pre-run `GET /health` gate; if `degraded`, the harness reports the failing dependency and exits `2`.
- Per-type + micro/macro **Precision/Recall/F1** (recall emphasized) and a confusion matrix.
- A **leak audit**: a leak count with pass/fail against the **zero-leak** bar. Exit `0` if zero leaks,
  exit `1` if any leak (the aggregate report is still written).
- A round-trip **restoration** breakdown (exact / inflection / fuzzy / base-only / missed) + document
  exact-restore rate.
- Artifacts in `thesis/images/` (figures + Typst tables + `aggregate.json`) and machine-readable results
  in the results dir.

## 4. Run Stage 2 (full chat flow with Echo)

```bash
nx run gateway-eval:evaluate -- --stage 2 --base-url http://localhost:8000 --provider echo
```
**Expected**: each document goes through `POST /v1/chat/completions` with `model="echo/echo"`; the harness
confirms (a) `input_anonymization.pseudonymized_content` is leak-free, (b) the restored answer reconstructs
the original document, (c) collects `anonymization_meta.timing_ms`. `llm_request` ≈ 0 ms (Echo is offline).

## 5. Full run (both stages)

```bash
nx run gateway-eval:evaluate -- --stage both
```
Produces the complete thesis evidence set. Use `--strict-spans` to make exact-span the headline detection
metric (overlap still reported alongside).

## 6. In-process validation (CI / no running container)

```bash
nx run gateway-eval:test
```
**Expected**: unit tests (span alignment overlap/exact edges, leak normalization with inflected/diacritic
forms, restoration classification, checksum-valid injection, gold-offset validation) **plus** one small
end-to-end Stage 1 + Stage 2 run that drives the gateway **ASGI app in-process** (via
`httpx.ASGITransport` over `fakeredis` + the Echo dependency-override) and asserts a complete
`AggregateResult` is produced — no network, no real keys, no docker.

## Validation checklist (maps to Success Criteria)

- [ ] Corpus: ≥ 50 docs, ≥ 500 entities, all 10 types, ≈ 60/40 split (SC-001).
- [ ] `--stage 1` yields per-type + micro/macro P/R/F1 + confusion matrix + leak count + restoration
      breakdown in one command (SC-002, SC-003, SC-005).
- [ ] Leak audit reports an exact count vs the zero-leak bar; an inflected original (`Kowalskiego`) is
      caught as a full leak (SC-004).
- [ ] Same `--seed` ⇒ identical corpus + gold; unchanged gateway ⇒ reproducible metrics (SC-006).
- [ ] Zero external egress; no real PII in any `thesis/images/` artifact (SC-007).
- [ ] `thesis/images/` has the four figure types + machine-readable results + error-analysis report
      (SC-008).
- [ ] `degraded` gateway ⇒ clear report, exit `2`, no misleading metrics (SC-009).
- [ ] Stage 2: every doc leak-free + answer restored + `timing_ms` captured (SC-010).
