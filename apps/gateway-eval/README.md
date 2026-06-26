# gateway-eval — PII Evaluation Harness (EPIC 8)

A **black-box** evaluation harness that drives the live anonymization gateway over its public HTTP API and
measures, against an **independent gold standard**, how well it detects, replaces, and restores Polish
civil-law-contract PII. It produces the evidence for the thesis evaluation chapter
(`thesis/content/06-testy-ewaluacja`).

It is **not** part of the production gateway and changes no gateway behaviour — it only calls public
endpoints. Ground truth comes **only** from the corpus gold standard, never from the gateway's own output
(anti-circularity).

## Two stages

- **Stage 1 (no LLM)** — `POST /v1/detect`, `/v1/pseudonymize`, `/v1/depseudonymize`: detection P/R/F1 +
  confusion matrix, the inflection-aware PII-leak audit (zero-leak bar), round-trip restoration, wall-clock
  latency per endpoint.
- **Stage 2 (full flow)** — `POST /v1/chat/completions` with `model="echo/echo"` (the deterministic Echo
  provider): verify the integrated pipeline is leak-free and restores, collect `anonymization_meta.timing_ms`.

## Run

```bash
nx run gateway-eval:install                       # sync deps (+ path dep on gateway-api)
nx run gateway-eval:build-corpus                  # offline, seeded synthetic corpus
nx run gateway-eval:evaluate -- --stage both      # against http://localhost:8000
nx run gateway-eval:test                           # in-process unit + e2e tests
```

For Stage 2 against the live stack, the gateway must expose the additive `echo/` provider route (see
`specs/008-gateway-eval-harness/contracts/gateway-echo-route.md`); send `model: "echo/echo"`. Rebuild the
gateway image after adding the route.

## Data handling (RODO / GDPR)

The evaluation runs **fully offline** (Echo provider, no external egress). The real 40% of the corpus lives
under `gateway_eval/corpus/data/real/` and is **git-ignored** — real contracts and any gold standard
containing real originals are never committed and never published. Only **aggregate metrics** and
**redacted/pseudonymized** examples reach `thesis/images/`. The committed synthetic corpus alone meets the
≥50-document / ≥500-instance floor, so CI and reproducibility runs need no real data.
