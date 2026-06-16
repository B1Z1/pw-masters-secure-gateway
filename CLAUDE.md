## What This Is

A gateway proxy that sits between the user and external LLM providers. It automatically detects personally identifiable
information (PII) in user messages, replaces it with realistic synthetic data before sending to the LLM, and restores
the original values in the response.

Built as a master's thesis project. Use case: analysis of Polish civil law contracts.

<!-- SPECKIT START -->
Active feature: **002-pii-detection-engine** (EPIC 2 — PII Detection Engine for Polish civil-law
contracts). For technologies, project structure, shell commands, and design decisions, read the
current plan and its artifacts:

- Plan: `specs/002-pii-detection-engine/plan.md`
- Spec: `specs/002-pii-detection-engine/spec.md` (+ Clarifications session 2026-06-16)
- Research & decisions (Presidio/spaCy PL wiring, scoring bands, checksums, overlap): `specs/002-pii-detection-engine/research.md`
- Data model (DetectedEntity DTO, metadata, thresholds): `specs/002-pii-detection-engine/data-model.md`
- Contracts: `specs/002-pii-detection-engine/contracts/` (detect.openapi, recognizers, thresholds, health-readiness)
- Quickstart / validation: `specs/002-pii-detection-engine/quickstart.md`
- Requirements checklist: `specs/002-pii-detection-engine/checklists/requirements.md`

EPIC 2 adds a Polish-only PII **detection** layer on top of the EPIC 1 runtime: given a text string it
returns detected entities (PERSON, LOCATION, EMAIL, PHONE, DATE_TIME, PESEL, NIP, REGON, bank account,
postal address) with type, start/end offsets, an explainable confidence score, the exact matched text,
and metadata (e.g. PESEL gender, REGON variant). Detection ONLY — no substitution, storage, or LLM
calls. Recall over precision; per-type confidence thresholds configurable without restart. A debug
endpoint surfaces detections for manual review; the existing `/health` `spacy_model` dependency check
becomes real (overall status degrades when the language model is not loaded).

Foundational infrastructure (EPIC 1, still in force):

- Plan: `specs/001-infrastructure-runtime/plan.md` (also: spec, research, data-model, contracts, quickstart)
- Stack: Nx integrated monorepo; backend `apps/gateway-api` (Python 3.12, FastAPI, `pydantic-settings`,
  async redis, uv); frontend `apps/gateway-ui` (React 18 + TypeScript + Vite, nginx in prod); Redis 7;
  Docker Compose (network `pw-masters-secure-gateway`).
<!-- SPECKIT END -->
