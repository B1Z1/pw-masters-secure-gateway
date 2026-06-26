# Contract: Gold-standard JSONL schema

The single source of ground truth, shared by synthetic and real documents (FR-008). One JSON object per
line. Full model + validation in [data-model.md](../data-model.md) §1.

## Line schema

```json
{
  "doc_id": "syn-najem-001",
  "source": "synthetic",
  "contract_type": "najem",
  "text": "Umowa najmu zawarta w dniu 12 marca 2024 r. ... Najemcą jest Jan Kowalski, PESEL 90010112345 ...",
  "entities": [
    { "type": "DATE_TIME", "start": 27, "end": 41, "text": "12 marca 2024 r." },
    { "type": "PERSON",    "start": 61, "end": 73, "text": "Jan Kowalski" },
    { "type": "PESEL",     "start": 81, "end": 92, "text": "90010112345" }
  ]
}
```

## Rules (hard errors on violation)

1. `source ∈ {"synthetic","real"}`; `type ∈` the 10 canonical types (see below).
2. Offsets are **character** offsets into `text`; `0 <= start < end <= len(text)`.
3. **Offset/text invariant**: `text[start:end] == entity.text` for every entity. A mismatch is a hard
   load-time error (no silent skip).
4. `doc_id` unique within the corpus.
5. Same-type entities must not overlap; different-type adjacency/overlap is allowed.

## Canonical entity vocabulary (FR-009)

`PERSON, LOCATION, ADDRESS, PESEL, NIP, REGON, BANK_ACCOUNT, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME`.

Gateway-emitted labels are mapped onto these via the versioned alias map (research D8); unmapped gateway
labels are reported, never silently coerced.

## Corpus-level targets (warn, not fail)

`>= 50` documents, `>= 500` entities, all 10 types represented, synthetic/real ≈ 60/40. A run against a
smaller corpus still works (so the harness is testable on a sample) but emits a shortfall warning.

## Provenance / storage

- `source="synthetic"` gold → committed under `corpus/data/synthetic/` (versioned, D7).
- `source="real"` gold (contains real originals) → `corpus/data/real/`, **git-ignored**, never published
  (D6). Manually annotated by the researcher to this exact schema; the real loader enforces rules 1–5.
