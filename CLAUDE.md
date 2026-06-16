## What This Is

A gateway proxy that sits between the user and external LLM providers. It automatically detects personally identifiable
information (PII) in user messages, replaces it with realistic synthetic data before sending to the LLM, and restores
the original values in the response.

Built as a master's thesis project. Use case: analysis of Polish civil law contracts.

<!-- SPECKIT START -->
Active feature: **001-infrastructure-runtime** (EPIC 1 — Infrastructure and Runtime Environment).
For technologies, project structure, shell commands, and design decisions, read the current plan
and its artifacts:

- Plan: `specs/001-infrastructure-runtime/plan.md`
- Spec: `specs/001-infrastructure-runtime/spec.md`
- Research & decisions (incl. image-size Risk R1): `specs/001-infrastructure-runtime/research.md`
- Data model: `specs/001-infrastructure-runtime/data-model.md`
- Contracts: `specs/001-infrastructure-runtime/contracts/` (health, environment, compose-services)
- Quickstart / validation: `specs/001-infrastructure-runtime/quickstart.md`

Stack (this epic): Nx integrated monorepo; backend `apps/gateway-api` (Python 3.12, FastAPI,
`pydantic-settings`, async redis, uv); frontend `apps/gateway-ui` (React 18 + TypeScript + Vite,
nginx in prod); Redis 7; Docker Compose (network `pw-masters-secure-gateway`).
<!-- SPECKIT END -->
