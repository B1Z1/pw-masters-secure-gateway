# Contract: Gateway HTTP endpoints consumed by the harness

The harness is a **client** of these existing gateway endpoints. It depends only on the fields below;
the gateway is otherwise frozen. Base URL configurable (default `http://localhost:8000`). No auth.

## `GET /health` — pre-run gate (FR-005)

Always HTTP 200. The harness reads:
```json
{ "status": "ok" | "degraded", "dependencies": { "redis": "ok|unavailable", "spacy_model": "ok|unavailable" } }
```
**Rule**: if `status != "ok"` (or the call fails/times out), the harness reports the degraded dependency
set and **exits without scoring** (no misleading metrics).

## `POST /v1/detect` — Stage 1 detection (gate-exempt; needs the spaCy model)

Request: `{ "text": "<document text>" }`
Response `200`:
```json
{ "entities": [ { "entity_type": "PERSON", "start": 12, "end": 24, "score": 0.95, "text": "Jan Kowalski", "lemma": null, "case": null, "metadata": {} } ] }
```
`503` while the model is not ready → recorded per-document as an error, not scored. The harness uses
`entity_type/start/end` (normalized via the alias map) as the **prediction** to align to gold.

## `POST /v1/pseudonymize` — Stage 1 outbound text + offsets (needs Redis)

Request: `{ "text": "<document text>", "session_id": "<fresh hex>" }`
Response `200`:
```json
{ "pseudonymized_text": "<outbound text with fakes>",
  "entities_replaced": [ { "entity_type": "PERSON", "original": "Jan Kowalski", "fake": "Piotr Nowak", "start": 12, "end": 24 } ],
  "session_id": "<hex>" }
```
The harness audits `pseudonymized_text` for leaks (against gold originals). `entities_replaced` is **not**
used as a detection answer key (anti-circularity, D1).

## `POST /v1/depseudonymize` — Stage 1 round-trip (needs Redis)

Request: `{ "text": "<pseudonymized_text from the same session>", "session_id": "<same hex>" }`
Response `200`: `{ "restored_text": "<originals restored>", "session_id": "<hex>" }`
The harness compares `restored_text` to the original document to classify restoration outcomes.

## `POST /v1/chat/completions` — Stage 2 full flow (needs Redis; `model: "echo/echo"`)

Request:
```json
{ "messages": [ { "role": "user", "content": "<document text>" } ], "session_id": "<fresh hex>", "model": "echo/echo" }
```
Response `200` (fields the harness reads):
```json
{ "choices": [ { "index": 0, "message": { "role": "assistant", "content": "<restored answer>" }, "finish_reason": "stop" } ],
  "session_id": "<hex>",
  "input_anonymization": { "pseudonymized_content": "<outbound text for the user turn>", "replacements": [ … ] },
  "anonymization_meta": { "entities_detected": { "PERSON": 2 }, "total_entities": 2, "provider": "echo",
    "timing_ms": { "ner_analysis": 0.0, "fake_generation": 0.0, "redis_write": 0.0, "llm_request": 0.0, "deanonymization": 0.0, "total": 0.0 } } }
```
Stage 2 checks: (a) `input_anonymization.pseudonymized_content` is **leak-free** vs gold; (b) the restored
`choices[0].message.content` reconstructs the original document (Echo echoes the pseudonymized user turn →
gateway restores it); (c) harvest `anonymization_meta.timing_ms`. Error bodies preserve `session_id`
(`{detail, session_id}`) → recorded per-document.

## `DELETE /v1/sessions/{session_id}` — cleanup (needs Redis)

Called after each document (both stages) to drop the session mapping and keep Redis clean. Any status is
acceptable; failures are logged, not fatal.

## `GET /v1/sessions/{session_id}/mappings` — optional debug only

May be called for the **error-analysis appendix** of a synthetic doc (never relied upon for scoring, never
for `source="real"`). Optional.
