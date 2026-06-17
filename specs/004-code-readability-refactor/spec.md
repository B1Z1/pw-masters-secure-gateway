# Feature Specification: Code Readability Refactor — Naming & Module Decomposition

**Feature Branch**: `im/04-refactor-structure-and-naming-convention`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Chciałbym zrobić review aplikacji apps/gateway-api. Review ma polegać na czytelności kodu, czyli nazwa plików, nazwa zmiennych, czy klasa/plik jest za duży i nie warto to rozbić. Uwagi: (1) ogólne nazewnictwo plików (encryption, matching, store) nic nie mówi — chcę nazwy, które mówią o sobie więcej; (2) zmienne/metody mają mieć pełne nazwy, nie skrócone — kod ma być czysty i samodokumentujący się, zgodny z zasadami clean code, i na tej podstawie chcę stworzyć rule dla agentów na przyszłość; (3) review czytelności pliku apps/gateway-api/gateway_api/pseudonym_vault/store.py — wydaje się za duży."

## User Scenarios & Testing *(mandatory)*

This is a **readability refactor** of the existing `gateway-api` backend. It changes how the code
reads, not what it does. The people who benefit are the **thesis author** (maintaining and defending
the code), **thesis reviewers** (reading the code without prior context), and **future AI coding
agents** (which must extend the code in the same style). Behavior, public endpoints, and persisted
data formats stay identical throughout.

### User Story 1 - Module & file names that state their purpose (Priority: P1)

A developer scanning the `gateway-api` source can tell what each file does from its name alone,
without opening it. Generic, low-information names such as `encryption`, `matching`, `store`,
`keys`, and `session` are replaced with names that describe the specific responsibility they hold
(for example, the role each plays inside the pseudonym vault), so the file tree itself documents the
module structure.

**Why this priority**: File names are the first and cheapest layer of documentation. Fixing them
gives the largest readability gain for the least risk and immediately addresses the user's primary
complaint.

**Independent Test**: Pick any module file in `gateway_api/` and ask a reader unfamiliar with the
code to state its responsibility from the name alone. The story succeeds when every file's purpose
is correctly inferable from its name, and the application still imports and runs (all existing tests
pass after import paths are updated).

**Acceptance Scenarios**:

1. **Given** the current `pseudonym_vault` package with files named `encryption.py`, `matching.py`,
   `store.py`, `keys.py`, `session.py`, **When** the refactor is complete, **Then** each file has a
   name that conveys its specific responsibility and no generic single-concept name remains
   unjustified.
2. **Given** a renamed module, **When** the test suite and application start-up run, **Then** every
   import resolves and behavior is unchanged (no test assertion needs editing — only import paths).
3. **Given** the full `gateway_api/` tree, **When** a reviewer reads only the file names, **Then**
   they can describe the module layout without opening any file.

---

### User Story 2 - Full, intention-revealing identifiers + a reusable agent rule (Priority: P2)

Variables, parameters, methods, and functions use complete, unabbreviated, intention-revealing
names so the code reads like prose and no comment is needed to explain *what* a line does. Cryptic
or truncated identifiers (e.g. `hkey`, `mkey`, `fwd`, `_enc`, `_gen`, `_seal`/`_open`, `ob`,
`cs`/`ss`, `d`, `rec`, `fmap`) are replaced. The conventions applied are then captured as a written
**naming rule for AI coding agents**, so future generated code follows the same standard
automatically.

**Why this priority**: Identifier names are where the user spends the most reading effort, and the
agent rule turns a one-time cleanup into a durable standard. It depends on no other story but is
broader in blast radius than the file renames, hence P2.

**Independent Test**: Sample a function from each package and confirm a reader can follow it without
explanatory comments; then have a coding agent (or person) apply the new rule to a fresh snippet and
confirm it reproduces the same naming style.

**Acceptance Scenarios**:

1. **Given** a method currently using abbreviated locals, **When** the refactor is complete,
   **Then** every identifier is a full, pronounceable, intention-revealing word or phrase consistent
   with the agreed convention.
2. **Given** a block that previously needed a comment to explain *what* it does, **When** renamed,
   **Then** the comment is removed because the code is self-explanatory (comments that explain *why*
   may remain).
3. **Given** the written agent naming rule, **When** a future agent generates new `gateway-api`
   code, **Then** following the rule yields identifiers consistent with the refactored codebase.

---

### User Story 3 - Decompose the oversized vault store (Priority: P3)

The single ~360-line `pseudonym_vault/store.py` is split into cohesive units, each with one
nameable responsibility (for example: encryption envelope helpers, coreference resolution,
fake-value generation with collision handling, restore/de-pseudonymization, session metadata, and
the public store facade). A reader can hold any one unit in their head at once, and the public entry
point used by the rest of the app stays stable.

**Why this priority**: The split is the highest-effort, highest-risk change and benefits from the
naming conventions from US1/US2 being settled first. It is still independently valuable: it directly
answers the user's "this file is too big" concern.

**Independent Test**: Confirm `store.py` is divided into focused units each below the agreed
readable size, every unit has a single describable responsibility, and the public store interface
plus all tests behave exactly as before.

**Acceptance Scenarios**:

1. **Given** today's `store.py` mixing encryption helpers, coreference, generation/collision,
   restore, and metadata, **When** the refactor is complete, **Then** each of those concerns lives
   in its own appropriately named unit.
2. **Given** the decomposition, **When** the rest of the application and the test suite run,
   **Then** the public store behavior is unchanged and no resulting unit exceeds the agreed readable
   size threshold.
3. **Given** a new contributor, **When** they open any one of the resulting units, **Then** they can
   understand its responsibility in isolation without reading the others.

---

### Edge Cases

- **Behavior preservation**: Renames and splits MUST NOT change the observable behavior of the two
  debug routes (`/v1/pseudonymize`, `/v1/depseudonymize`) or the detection pipeline they reuse.
- **Persisted-format stability**: Redis field prefixes/layout, the AES-256-GCM encryption envelope,
  and the HMAC forward-field naming MUST remain byte-compatible — no data migration, and a session
  written before the refactor remains readable after it.
- **Constitution constraints**: No PII may appear in logs (Principle VIII) and reversibility +
  encryption scope (Principle III) MUST remain intact after any rename or split.
- **Broken references**: A rename that misses a reference must be caught — the application start-up
  and full test suite are the safety net.
- **Idiomatic exceptions**: Where an abbreviation is a widely-accepted idiom (e.g. a short loop
  index, well-known acronyms like PII/NIP/PESEL/HMAC/TTL), it is retained intentionally rather than
  expanded into something less clear.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every module/file name under `gateway_api/` MUST describe its specific responsibility;
  generic low-information names (`encryption`, `matching`, `store`, `keys`, `session`, and any
  others found during review) MUST be replaced with intention-revealing names or have a documented
  justification for keeping them.
- **FR-002**: All identifiers (variables, parameters, functions, methods, attributes) MUST use
  complete, unabbreviated, intention-revealing names consistent with clean-code principles;
  truncated or cryptic names MUST be eliminated except where they are widely-accepted idioms or
  domain acronyms (PII, PESEL, NIP, REGON, HMAC, TTL, etc.).
- **FR-003**: Following from FR-002's full, intention-revealing names, code MUST be self-documenting
  to the point that comments explaining *what* the code does are no longer necessary and are removed;
  comments explaining *why* (rationale, references to research decisions, constitution exceptions)
  MAY remain.
- **FR-004**: `pseudonym_vault/store.py` MUST be decomposed into multiple cohesive units, each with a
  single nameable responsibility, such that no resulting unit exceeds an agreed readable size
  threshold and each can be understood in isolation.
- **FR-005**: A reusable **naming-convention rule for AI coding agents** MUST be created as a
  markdown file in the project's `.claude/rules/` directory, capturing the file-naming and
  identifier-naming conventions applied in this refactor. The rule MUST be auto-loaded into agent
  context (verifiable via `/memory`) and SHOULD be path-scoped with `paths` frontmatter to the
  backend Python tree (e.g. `apps/gateway-api/**/*.py`) so it only consumes context when an agent
  works on that code.
- **FR-006**: The refactor MUST preserve all observable behavior — every pre-existing automated test
  MUST pass without changes to its assertions (only import paths and internal symbol references may
  change).
- **FR-007**: The refactor MUST NOT alter any persisted data format (Redis field layout, encryption
  envelope, HMAC field naming); no migration is required and pre-refactor sessions stay readable.
- **FR-008**: Every rename (file or symbol) MUST update all references across the codebase so the
  application imports, starts, and serves requests successfully.
- **FR-009**: The refactor MUST keep all Constitution principles satisfied, in particular VIII (no
  PII in logs) and III (reversibility + encryption scope).
- **FR-010**: The naming/decomposition refactor MUST be applied across the **entire `gateway_api`
  codebase** (all packages: `pseudonym_vault/`, `pii_detection/`, `pseudonym_generation/`, `api/`,
  and the top-level modules), not only the `pseudonym_vault` package where the example problems were
  first noticed.

### Key Entities *(include if feature involves data)*

- **Module naming convention**: The rule that maps a file's responsibility to a descriptive,
  intention-revealing file name; the standard US1 enforces.
- **Identifier naming convention**: The rule for full, unabbreviated, intention-revealing names for
  variables, parameters, and methods; the standard US2 enforces.
- **Agent naming rule (deliverable)**: A written artifact encoding both conventions so future AI
  coding agents reproduce them; the durable output of US2.
- **Vault store responsibilities**: The distinct concerns currently bundled in `store.py`
  (encryption envelope, coreference resolution, fake generation + collision handling, restore,
  session metadata, public facade) that US3 separates into cohesive units.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of module files in scope can have their purpose correctly stated by a reader from
  the file name alone, without opening the file.
- **SC-002**: Zero abbreviated or cryptic identifiers remain in scope (measured against the agreed
  convention's idiom/acronym allowlist).
- **SC-003**: 100% of pre-existing automated tests pass after the refactor with no edits to their
  assertions, demonstrating behavior was preserved.
- **SC-004**: The previously largest file (`store.py`, ~360 lines) is split so that every resulting
  unit is below the agreed readable-size threshold and each maps to one stated responsibility.
- **SC-005**: Every comment that merely restated *what* the adjacent code does has been removed; a
  spot check of any package finds remaining comments explain only *why*.
- **SC-006**: The agent naming rule exists and is verifiable: a reviewer applying it to a sample
  snippet, independently of the author, produces naming consistent with the refactored code.
- **SC-007**: A new reader can locate the code responsible for a given vault concern (e.g.
  "where are originals restored?") in under one minute using file names alone.

## Assumptions

- This is a **pure refactor**: no functional, behavioral, or API change is intended or permitted; the
  existing automated test suite is the behavior oracle.
- The technology stack and Constitution are fixed constraints (Python 3.12 / FastAPI; AES-256-GCM
  envelope; Redis HASH-per-session layout; HMAC forward fields) and are not revisited here.
- "Readable size threshold" for files/units will be agreed during planning as a soft guideline (split
  by responsibility/cohesion rather than a hard line count); no constitutional limit exists today.
- Domain acronyms and widely-accepted idioms (PII, PESEL, NIP, REGON, NRB, HMAC, TTL, short loop
  indices) are acceptable and are NOT treated as "abbreviations to expand".
- The agent naming rule is a documentation artifact (not executable tooling); enforcement remains by
  review, not by an automated linter, unless added as a later follow-up. It lives in `.claude/rules/`
  because Claude Code auto-loads every `.md` there into context at session start (confirmed against
  the official Claude Code memory docs), with optional `paths` frontmatter for file-scoped loading.
- The refactor scope is the entire `gateway_api` backend (all packages); the `gateway-ui` frontend is
  out of scope for this feature.
