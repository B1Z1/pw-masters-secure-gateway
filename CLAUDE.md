## What This Is

A gateway proxy that sits between the user and external LLM providers. It automatically detects personally identifiable
information (PII) in user messages, replaces it with realistic synthetic data before sending to the LLM, and restores
the original values in the response.

Built as a master's thesis project. Use case: analysis of Polish civil law contracts.

<!-- SPECKIT START -->
Active feature: **004-code-readability-refactor** — a behavior-preserving readability refactor of the
`apps/gateway-api` backend: role-revealing file names in `gateway_api/pseudonym_vault/` (e.g.
`store.py`→`mapping_store.py`, `encryption.py`→`aes_gcm_encryption.py`), full intention-revealing
identifiers across `gateway_api`, decomposition of the oversized `store.py`/`MappingStore` into a
thin facade + focused collaborators (encrypted-JSON codec, Redis session repository, coreference
resolver, unique-fake factory, original-surface restorer), and an auto-loaded agent naming rule at
`.claude/rules/python-naming-conventions.md`. No behavior/API/wire-format change — the existing test
suite plus the Redis field layout and AES-256-GCM envelope are the regression contract. For design
and decisions, read the plan and its artifacts:

- Plan: `specs/004-code-readability-refactor/plan.md`
- Spec: `specs/004-code-readability-refactor/spec.md` (+ Clarifications session 2026-06-17: rule lives in `.claude/rules/`; refactor scope = whole `gateway_api`)
- Research (vault file renames, by-domain decomposition of store.py, rule location/enforcement): `specs/004-code-readability-refactor/research.md`
- Data model (module responsibility model, store.py method-migration map, identifier rename catalog): `specs/004-code-readability-refactor/data-model.md`
- Contract (frozen public API + Redis/encryption wire formats): `specs/004-code-readability-refactor/contracts/preserved-interfaces.md`
- Quickstart / validation: `specs/004-code-readability-refactor/quickstart.md`
- Requirements checklist: `specs/004-code-readability-refactor/checklists/requirements.md`

Prior epics remain in force and are the code under review: EPIC 3 substitution + reversible mapping
(`specs/003-fake-data-generator/` — Faker `pl_PL` builders, AES-256-GCM-encrypted Redis HASH per
session, debug routes `POST /v1/pseudonymize` + `/v1/depseudonymize`, NO LLM), EPIC 2 detection
(`specs/002-pii-detection-engine/`), EPIC 1 infrastructure (`specs/001-infrastructure-runtime/`).

Stack: Nx integrated monorepo; backend `apps/gateway-api` (Python 3.12, FastAPI, `pydantic-settings`,
async redis, uv); frontend `apps/gateway-ui` (React 18 + TypeScript + Vite, nginx in prod); Redis 7;
Docker Compose (network `pw-masters-secure-gateway`).
<!-- SPECKIT END -->
