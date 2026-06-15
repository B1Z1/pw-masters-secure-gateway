# Feature Specification: EPIC 1 — Infrastructure and Runtime Environment

**Feature Branch**: `001-infrastructure-runtime`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "EPIC 1 — Infrastructure and Runtime Environment of the LLM anonymization gateway. A monorepo containing a Python/FastAPI backend (`gateway-api`) and a React SPA frontend (`gateway-ui`) backed by Redis, all started with a single `docker compose up`. Provides three Docker services on an internal network, a hot-reload local development mode, environment-driven configuration with fail-fast validation, and a health endpoint that reports dependency status and degrades gracefully."

## Overview

This epic delivers the foundational runtime environment for the anonymization gateway: the way the system is started, configured, and observed — before any anonymization logic exists. It produces a reproducible, single-command stack for demonstration/deployment, a fast inner-loop development mode for active work, environment-driven configuration with safety guarantees on secrets, and a health surface that lets orchestration and developers tell whether the system and its dependencies are working.

No PII detection, substitution, or LLM proxying is built in this epic. Those arrive in later epics. The health endpoint's dependency checks are wired so the substitution engine's checks (e.g., the NER model) can be plugged in later without touching the endpoint itself.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch the entire system with one command (Priority: P1)

An operator (or a thesis reviewer) clones the repository, copies the example configuration file to a real one, fills in the required secret values, and runs a single start command. Within about a minute the whole system is up and healthy: the web interface is reachable in a browser, the backend is reachable behind it, and the session store runs privately inside the stack without being exposed to the host machine.

**Why this priority**: This is the headline deliverable of the epic and the primary way the project is demonstrated and evaluated. Without it, nothing else in the system can be shown end to end. It is the minimum viable slice: a reproducible, one-command running system.

**Independent Test**: From a clean checkout on a machine with the container runtime installed, copy the example config, provide a valid encryption key and password, run the single start command, and confirm all three services report healthy and the web interface loads — with no manual steps beyond editing the config file.

**Acceptance Scenarios**:

1. **Given** a clean checkout and a valid configuration file, **When** the operator runs the single start command, **Then** all three services (backend, frontend, session store) reach a healthy state within 60 seconds.
2. **Given** the stack is running, **When** the operator opens the web interface address in a browser, **Then** the single-page application loads, and requests it makes to the backend are routed through to the backend service.
3. **Given** the stack is running, **When** the operator inspects exposed host ports, **Then** the web interface and backend are reachable on their published ports and the session store is **not** reachable from the host.
4. **Given** the configuration file has not been created yet, **When** the operator attempts to start the stack, **Then** the operator is able to start it immediately after copying the documented example file and filling in values, with no other manual setup.
5. **Given** the services have inter-dependencies, **When** the stack starts, **Then** the session store becomes healthy before the backend starts, and the backend becomes healthy before the frontend starts.

---

### User Story 2 - Develop locally with a fast hot-reload loop (Priority: P2)

A developer working on the codebase needs to change backend or frontend source code and see the effect immediately, without rebuilding any container image. They run only the session store inside the container runtime and run the backend and frontend natively on their machine, each with hot reload. Source edits are reflected on the next request/refresh.

**Why this priority**: Rebuilding images on every code change is unacceptable for active development and would make the project impractical to build. This mode is essential to development velocity, but the system can still be demonstrated (P1) without it, so it ranks second.

**Independent Test**: Start only the session store in a container, start the backend and frontend natively per the documented workflow, edit a line in each, and confirm both reload automatically and the change is observable without any image rebuild.

**Acceptance Scenarios**:

1. **Given** the developer wants only the session store containerized, **When** they start just that service, **Then** the session store runs in a container and is reachable from the natively-running backend on the host.
2. **Given** the backend runs natively in development mode, **When** the developer edits a backend source file, **Then** the backend reloads automatically and serves the change without an image rebuild or container restart.
3. **Given** the frontend runs natively in development mode, **When** the developer edits a frontend source file, **Then** the browser reflects the change via hot reload, and the frontend's calls to the backend are proxied to the natively-running backend.
4. **Given** development mode is active, **When** the stack is brought up with development overrides, **Then** the frontend container is excluded (the developer runs it natively instead) and the session store is reachable on the host.
5. **Given** the monorepo tooling, **When** the developer invokes the per-project commands, **Then** the backend server starts locally and the frontend development server starts locally as documented.

---

### User Story 3 - Observe health and survive dependency failures (Priority: P3)

An operator, an orchestration system, or a developer queries the system's health surface to learn whether it and its dependencies are working. When a dependency (the session store) is unavailable, the system keeps running and reports itself as degraded rather than crashing; it refuses to serve normal traffic but never gets restarted for a transient dependency blip. When configuration is invalid in a way that would compromise security, the system refuses to start at all.

**Why this priority**: Health observability and graceful degradation make the system operable and trustworthy, and the fail-fast-on-bad-secret behavior protects the security guarantees of later epics. These behaviors build on a running system (P1) and so come after it.

**Independent Test**: Query the health endpoint while everything is up (expect "ok"); kill the session store and query again (expect "degraded", still HTTP 200, and normal endpoints rejected); start the backend with an invalid encryption key (expect immediate non-zero exit before serving traffic).

**Acceptance Scenarios**:

1. **Given** all dependencies are healthy, **When** the health endpoint is queried, **Then** it responds with HTTP 200 and a body showing every dependency as available and overall status "ok".
2. **Given** the session store is unavailable, **When** the health endpoint is queried, **Then** it still responds with HTTP 200 but reports the session store as unavailable and overall status "degraded".
3. **Given** the session store is unavailable, **When** any non-health endpoint is requested, **Then** the request is rejected with HTTP 503 and the backend process does not crash.
4. **Given** the session store was unavailable and then becomes reachable again, **When** the health endpoint is queried, **Then** it reports the session store as available again without restarting the backend.
5. **Given** an invalid encryption key in configuration, **When** the backend starts, **Then** it refuses to start, exits with a non-zero code within 5 seconds, and never serves any request.
6. **Given** a configured LLM provider key is empty, **When** the backend starts, **Then** startup succeeds, and an error related to the missing key surfaces only when that provider is first used.

---

### Edge Cases

- **Session store address missing from configuration**: The backend still starts and serves the health endpoint, but rejects all non-health requests with HTTP 503.
- **Session store unreachable at runtime** (crashed, network partition, killed container): The backend continues running, does not crash, reports degraded health, and returns HTTP 503 for normal traffic.
- **Invalid encryption key** (not valid base64, or not exactly 32 bytes when decoded): The backend refuses to start and exits with a non-zero code — a hard stop, not a degraded run.
- **Empty/missing LLM provider keys**: No effect at startup; the error appears only when that specific provider is first invoked (a later-epic concern, but the configuration must allow blanks).
- **Session store recovers after an outage**: Health and normal traffic recover automatically on subsequent requests without a backend restart.
- **A published host port is already in use** (web interface, backend, or the development session-store port): Startup of the affected service fails with a clear port-conflict error; this is surfaced to the operator, not silently swallowed.
- **Frontend deep link / page refresh on a client-side route**: The web server serves the application shell so client-side routing handles the path (no server 404 for application routes).
- **Native backend cannot reach the containerized session store in development**: Occurs if the development override does not expose the session store on the host; the documented development workflow must make the store reachable from the host.
- **Provider base URL pointing at the host machine** (e.g., a locally-run model server): Reachability from inside containers depends on the host-gateway mapping; documented as an environment-dependent assumption (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

#### Orchestration & single-command startup

- **FR-001**: The system MUST start all three services — backend, frontend, and session store — with a single start command, requiring no manual steps beyond creating the configuration file from the shipped example.
- **FR-002**: The three services MUST run on a single dedicated internal network named for the project so they can address each other by service name.
- **FR-003**: The session store MUST NOT be exposed on a host port in the default (production) startup; it MUST be reachable only by other services on the internal network.
- **FR-004**: Service startup order MUST be enforced by dependency conditions: the session store MUST be healthy before the backend starts, and the backend MUST be healthy before the frontend starts.
- **FR-005**: The frontend service MUST serve the built single-page application with a fallback that routes unknown application paths to the application shell, and MUST forward the application's backend-bound requests to the backend service.
- **FR-006**: Each service MUST expose its own health/readiness signal that the orchestration uses to determine the "healthy" condition driving startup order.
- **FR-007**: The full stack MUST reach an all-healthy state within 60 seconds of the start command on a typical development machine.

#### Local development mode

- **FR-008**: The system MUST provide a development mode in which only the session store runs in a container while the backend and frontend run natively on the host with hot reload.
- **FR-009**: Development mode MUST expose the session store on a host port so the natively-running backend can reach it.
- **FR-010**: Development mode MUST allow backend source changes to be reflected without rebuilding any container image (live source reload).
- **FR-011**: Development mode MUST exclude the frontend container from the started services (the developer runs the frontend natively instead).
- **FR-012**: The native frontend development server MUST support hot reload and MUST proxy its backend-bound requests to the natively-running backend.
- **FR-013**: The developer MUST be able to start only the session store service on its own.
- **FR-014**: The monorepo tooling MUST provide per-project commands to (a) start the backend server locally, (b) start the frontend development server locally, and (c) run all project test suites together.
- **FR-015**: The repository MUST document the local development workflow (starting the session store, starting the backend natively, starting the frontend natively, and the addresses involved) in the README.

#### Environment configuration

- **FR-016**: All runtime configuration MUST be supplied through a single environment configuration file; no required configuration value may be hard-coded in source.
- **FR-017**: The repository MUST ship an example configuration file that documents every supported variable inline, and the real configuration file MUST be excluded from version control and never committed.
- **FR-018**: The configuration MUST support, at minimum: the session-store connection address, the session-store password, the session-store encryption key, the session time-to-live, the keys/base URLs for each supported LLM provider, the default provider, and the default model.
- **FR-019**: The encryption key MUST be validated at startup to be valid base64 that decodes to exactly 32 bytes; if it is not, the backend MUST refuse to start and exit with a non-zero code.
- **FR-020**: LLM provider keys MUST be optional at startup (no startup validation); a missing key MUST only cause an error when that provider is first used.
- **FR-021**: The example configuration MUST include guidance for generating a valid encryption key and MUST use clearly-placeholder defaults (never real secrets) for any pre-filled values.

#### Health & resilience

- **FR-022**: The backend MUST expose a health endpoint that ALWAYS responds with HTTP 200, regardless of dependency status.
- **FR-023**: The health response body MUST report an overall status and a per-dependency status for each tracked dependency (the session store and the substitution model).
- **FR-024**: The overall status MUST be derived by aggregation: if any single dependency is unavailable, the overall status MUST be "degraded"; only when all are available is it "ok".
- **FR-025**: The session-store health check MUST use a bounded timeout (about 1 second); any error or timeout MUST be reported as that dependency being unavailable rather than failing the request.
- **FR-026**: The substitution-model dependency check MUST be a placeholder for this epic that always reports available, and MUST be structured so a later epic can replace it with a real check without modifying the health endpoint logic.
- **FR-027**: When the session store is unavailable, every non-health endpoint MUST be rejected with HTTP 503; the health endpoint MUST remain exempt from this rejection.
- **FR-028**: The backend MUST NOT crash when the session store is missing from configuration or unreachable at runtime; it MUST keep serving the health endpoint and degrade gracefully.
- **FR-029**: The health endpoint MUST respond in under 500 milliseconds under normal conditions.
- **FR-030**: System logs produced by this infrastructure MUST contain only operational metadata (status, timings, error categories) and MUST NOT contain secret values such as the encryption key or session-store password.

#### Packaging & footprint

- **FR-031**: The backend and frontend MUST each be packaged as a runtime image whose build separates build-time tooling/dependencies from the final runtime artifacts, so the shipped image contains only what is needed to run.
- **FR-032**: The backend runtime image SHOULD be kept lean via multi-stage builds, but there is **no hard size cap**. The Polish substitution model is baked into the image (FR-033) and its footprint is accepted; the earlier <500 MB target is relaxed and informational only.
- **FR-033**: The backend image build MUST include the resources its substitution engine will require at runtime so the running container does not need to download them at startup.

### Key Entities *(include if feature involves data)*

- **Service**: A runnable unit of the system. There are three — the backend API, the frontend web interface, and the session store. Each has an address on the internal network, an optional published host port, a health signal, and a place in the startup order.
- **Environment configuration**: The set of named values that parameterize the running system (connection addresses, secrets, time-to-live, provider credentials, default provider/model). Sourced from a single file, with a documented example template and a never-committed real instance.
- **Health status report**: The structured result returned by the health endpoint — an overall status plus a per-dependency status map. Driven by live checks of the session store and a placeholder check of the substitution model.
- **Session store dependency**: The external store the backend depends on for session/mapping data in later epics. In this epic it is a tracked dependency whose availability governs degraded status and non-health request rejection; its encryption key and time-to-live are configured here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean checkout, an operator brings the entire system to an all-healthy state with a single command and no manual steps beyond filling in the configuration file, within 60 seconds.
- **SC-002**: The health endpoint returns a status response in under 500 milliseconds.
- **SC-003**: An invalid encryption key causes the backend to stop within 5 seconds with a non-zero exit code, before it serves any request.
- **SC-004**: With the system running, killing the session store leaves the backend answering the health endpoint (reporting "degraded") and rejecting all other requests with HTTP 503, with zero crashes; restoring the store returns the system to "ok" without a backend restart.
- **SC-005**: A developer changes backend source and frontend source and observes each change take effect via hot reload without rebuilding any container image.
- **SC-006**: The backend image builds successfully via a multi-stage build with the Polish model baked in; its size is recorded for reference (no upper-bound gate).
- **SC-007**: A single command runs both the backend and frontend test suites.
- **SC-008**: Per-project commands successfully start the backend server and the frontend development server individually.
- **SC-009**: No real secret value is ever present in version control; the committed example configuration contains only placeholders and the real configuration file is ignored by version control.
- **SC-010**: In the default startup, the session store is not reachable from the host, while the web interface and backend are reachable on their published ports.

## Assumptions

- **Container runtime available**: The target machine has a Compose-capable container runtime installed and running; the operator has rights to publish the documented host ports.
- **Single-host scope**: This epic targets a single-host Compose deployment (local/demo), not a multi-node orchestrator; horizontal scaling and production-grade orchestration are out of scope.
- **Health recovery is per-request**: Dependency status is re-evaluated on each health query and each gated request, so the system recovers from a transient session-store outage automatically without manual intervention or restart.
- **Substitution-model check is a stub**: For this epic the substitution-model dependency always reports available; the real check is delivered in the NER engine epic and must slot into the existing structure without changing the health endpoint.
- **Session store persistence not required here**: Session data is ephemeral and time-to-live bound; durable persistence/backup of the store is out of scope for this epic.
- **Host-gateway reachability for local provider**: A provider base URL pointing at the host machine (e.g., a locally-run model server) relies on a host-gateway mapping that is environment-dependent; on platforms where it is not provided automatically, an explicit mapping or documented limitation is required. This is noted, not solved, in this epic.
- **Synchronous request-response only**: Consistent with the project constitution, only synchronous request-response behavior is in scope; streaming is excluded.
- **Encryption key sizing supports later AES-256 use**: The 32-byte encryption key validated here is the key material the later session-mapping store will use; validating its size now prevents a downstream security failure.
- **Default provider/model placeholders**: The shipped example uses a documented default provider and model as placeholders; they can be overridden and are not validated for reachability in this epic.
