# Contract: AnonymizationPipeline (internal component)

**Feature**: EPIC 4 | `gateway_api/pipeline/anonymization_pipeline.py` | Programmatically callable
(FR-001) — consumed by `api/chat.py` now and by later epics. No HTTP dependency.

## Construction

`AnonymizationPipeline(engine: DetectionEngine, store: MappingStore)` — both reused, not reimplemented
(FR-002).

## Methods

### `async pseudonymize_text(session_id, text) -> (fake_text, list[Replacement])`
The EPIC 3 inbound core, **extracted** from `api/pseudonymize.py` (FR-003, research D8): detect PII →
`store.get_or_create` per entity → reverse-order splice. Empty/whitespace → `(text, [])`. `Replacement`
= `{entity_type, original, fake, start, end}` (offsets into the ORIGINAL text). The EPIC 3
`/v1/pseudonymize` handler is refactored to call this and MUST keep its response byte-identical
(regression contract; `test_pseudonymize_api` green).

### `async pseudonymize_messages(session_id, messages) -> list[ChatMessage]`
Applies `pseudonymize_text` to **every** message's `content` each turn (FR-005), roles preserved.
Deterministic re-pseudonymisation (same original → same fake) via session consistency (FR-006).

### `async depseudonymize_text(session_id, text) -> str`
Outbound stage: `store.restore_text(session_id, text, fuzzy=True)` — exact + inflection **first**
(unchanged EPIC 3 pass), then the bounded fuzzy fallback for PERSON/LOCATION (FR-004, FR-008–FR-015).

## Invariants

- **No-leak (FR-024, Constitution I)**: after `pseudonymize_messages`, no `content` contains any
  original mapped in the session.
- **No-PII-in-logs (Constitution VIII)**: only `session_id`, entity types/counts, timings.
- **Synchronous (Constitution V)**: outbound runs only on a complete answer.

## `MappingStore.restore_text` change (additive)

New keyword `fuzzy: bool = False`. Default `False` → current EPIC 3 behaviour (exact + inflection
only), so `/v1/depseudonymize` and existing tests are unchanged. `True` → after the exact loop, run
`FuzzyNameRestorer` over the PERSON/LOCATION reverse records. Redis layout + AES-256-GCM envelope
unchanged.
