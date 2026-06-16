# Contract: Threshold Configuration (Epic 2)

Per-entity-type minimum confidence thresholds. Applied as a **post-filter** after analysis + context
enhancement + overlap resolution (research D5). Held in a dedicated YAML file, **separate** from the
env-based `Settings` (spec clarification), read **live** so changes take effect without a restart
(FR-020). No Redis dependency.

## File

- **Shipped default**: `apps/gateway-api/gateway_api/detection/default_thresholds.yaml`.
- **Override**: set `DETECTION_THRESHOLDS_PATH` (new optional setting in `config.py`) to an absolute path.
- **Reload**: `thresholds.py` caches the parsed table keyed on the file's modification time (mtime); on
  the next request after the file changes, the new values apply. No process restart, no env change.

## Schema

```yaml
default: 0.30                 # float in [0.0, 1.0]; used for any entity_type not in `thresholds`
thresholds:                   # map<entity_type, float in [0.0, 1.0]>
  PESEL: 0.25
  NIP: 0.25
  REGON: 0.25
  POLISH_BANK_ACCOUNT: 0.25
  POLISH_ADDRESS: 0.35
  DATE_TIME: 0.30
  PERSON: 0.40
  LOCATION: 0.40
  EMAIL_ADDRESS: 0.40
  PHONE_NUMBER: 0.40
```

## Semantics

- Keep entity iff `score >= thresholds.get(entity_type, default)`.
- **`0.0`** → "paranoid": every candidate the recognizer produced for that type is returned (FR-022).
- **`1.0`** → disabled: nothing passes, because scores are clamped to ≤ 0.99 (research D6, FR-022).
- Defaults are deliberately **low** (recall over precision, Constitution II). The bad-checksum band
  (0.30) sits at/above the ID thresholds (0.25) so invalid-but-format-matching IDs are still surfaced
  (FR-014).

## Validation / failure handling

- Missing file or parse error → fall back to the shipped defaults and log a warning (no crash, no PII).
- Unknown entity types in the file → ignored. Out-of-range values → clamped to `[0.0, 1.0]`.
- The file contains **no secrets and no PII** — it is safe to commit the default file.
