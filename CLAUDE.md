## What This Is

A gateway proxy that sits between the user and external LLM providers. It automatically detects personally identifiable
information (PII) in user messages, replaces it with realistic synthetic data before sending to the LLM, and restores
the original values in the response.

Built as a master's thesis project. Use case: analysis of Polish civil law contracts.

<!-- SPECKIT START -->
Active feature: **003-fake-data-generator** (EPIC 3 — Realistic fake-data generator and reversible
session mapping store for Polish civil-law contracts). For technologies, project structure, shell
commands, and design decisions, read the current plan and its artifacts:

- Plan: `specs/003-fake-data-generator/plan.md`
- Spec: `specs/003-fake-data-generator/spec.md` (+ Clarifications session 2026-06-16)
- Research & decisions (lemma/Case via spaCy, suffix-table inflection, AES-256-GCM, HMAC field names, hash-per-session store, coreference, fuzzy restore, collisions): `specs/003-fake-data-generator/research.md`
- Data model (FakeValue, Session/meta, Mapping hash layout, DetectedEntity lemma/case delta, encryption envelope): `specs/003-fake-data-generator/data-model.md`
- Contracts: `specs/003-fake-data-generator/contracts/` (pseudonymize.openapi, mapping-store, generators, inflection, encryption)
- Quickstart / validation: `specs/003-fake-data-generator/quickstart.md`
- Requirements checklist: `specs/003-fake-data-generator/checklists/requirements.md`

EPIC 3 adds the **substitution + reversible-mapping** layer between Epic 2 detection and the Epic 4 LLM
proxy. Three new packages: `gateway_api/pseudonym_generation/` (Faker `pl_PL` builders → checksum-valid PESEL/NIP/
REGON/bank, valid phone, ±10y dates, gender-consistent names; pure suffix-table Polish inflection for
PERSON/LOCATION), `gateway_api/pseudonym_vault/` (one AES-256-GCM-encrypted Redis HASH per session, sliding 30-min
TTL, explicit clear, reviewer listing; originals encrypted, fakes clear as the reverse index, forward
field names a keyed HMAC), and two debug routes `POST /v1/pseudonymize` + `/v1/depseudonymize` (reuse
DetectionEngine, NO LLM). Epic 2's `DetectedEntity` gains `lemma`/`case` (from spaCy) for case-aware
substitution. Same original → same fake within a session; ambiguous surname-only → new person; these
routes REQUIRE Redis (Epic 1 gate applies). Previous detection epic (EPIC 2) remains in force:
`specs/002-pii-detection-engine/`.

Foundational infrastructure (EPIC 1, still in force):

- Plan: `specs/001-infrastructure-runtime/plan.md` (also: spec, research, data-model, contracts, quickstart)
- Stack: Nx integrated monorepo; backend `apps/gateway-api` (Python 3.12, FastAPI, `pydantic-settings`,
  async redis, uv); frontend `apps/gateway-ui` (React 18 + TypeScript + Vite, nginx in prod); Redis 7;
  Docker Compose (network `pw-masters-secure-gateway`).
<!-- SPECKIT END -->
