# Contract: Recognizers (Epic 2)

Per-recognizer behavioural contract consumed by `DetectionEngine`. Each custom recognizer lives in its
own module and is independently unit-tested (positive / negative / edge). Scoring follows the bands in
[../data-model.md](../data-model.md) §5; offsets/text always reference the original span (FR-003).

Legend: **Base score** = pre-context pattern score; context bonus (+0.20, label nearby) and the ≤0.99
clamp are applied by the engine. "Context words" feed the `LemmaContextAwareEnhancer`.

---

## PESEL — entity `PESEL`

- **Matches**: 11 digits, optional single spaces/dashes between groups.
- **Validation**: PESEL control sum on the normalized value. Valid → 0.80; invalid → 0.30 (**kept**, FR-014).
- **Context words**: `PESEL`, `nr PESEL`, `numer PESEL`.
- **Metadata**: `{ gender: male|female, birth_date: YYYY-MM-DD|null, checksum_valid, normalized }`.
- **Edges**: post-2000 dates (month +20 offset) → correct century; incoherent date → lower confidence, not dropped; random 11-digit passing checksum → accepted (over-detection OK).

## NIP — entity `NIP`

- **Matches**: 10 digits, optional separators (`123-456-32-18`, `1234563218`).
- **Validation**: NIP control sum; `control == 10` ⇒ invalid. Valid → 0.80; invalid → 0.30 (kept).
- **Context words**: `NIP`, `nr NIP`, `VAT`.
- **Metadata**: `{ checksum_valid, normalized }`.
- **Edges**: leading `0` is valid (FR-009) — no non-zero-first-digit rule.

## REGON — entity `REGON`

- **Matches**: 9 **or** 14 digits, optional separators.
- **Validation**: REGON-9 vs REGON-14 control sum (own weights each). Valid → 0.80; invalid → 0.30 (kept).
- **Context words**: `REGON`, `nr REGON`.
- **Metadata**: `{ variant: "9"|"14", checksum_valid, normalized }`.
- **Edges**: a 14-digit whose first 9 form a REGON-9 → the **14-digit** span wins overlap resolution (FR-023, D4).

## Polish bank account — entity `POLISH_BANK_ACCOUNT`

- **Matches**: 26 digits, optional `PL` prefix, optional spaces in 2+4×6 grouping; also a continuous 26-digit run.
- **Validation**: ISO 7064 mod-97. Valid → 0.80; invalid/none → 0.30 (kept).
- **Context words**: `nr rachunku`, `rachunek`, `konto`, `IBAN`, `nr konta`.
- **Metadata**: `{ format: IBAN|NRB, mod97_valid, normalized }`.
- **Edges**: `PL`-prefixed IBAN and bare 26-digit NRB both handled; a 26-digit run in non-banking context → low confidence (0.30), still surfaced.

## Polish address — entity `POLISH_ADDRESS`

- **Matches**: street prefix (`ul.`, `al.`, `pl.`, `os.`) + name + building/flat no. + postal code `XX-XXX` + city; single- or multi-line. Also postal code + city without a street.
- **Validation**: none (no checksum). With street → 0.60; without street → 0.40.
- **Context words**: `ul.`, `al.`, `pl.`, `adres`, `zamieszkały`, `siedziba`.
- **Metadata**: `{ has_street: bool, postal_code: "XX-XXX"|null }`.
- **Edges**: a street that is a surname (`ul. Kowalskiego`) is part of the address — no separate PERSON; a contained city/LOCATION is subsumed by the address span (FR-024, FR-025, D4).

## Polish date — entity `DATE_TIME`

- **Matches**: numeric `DD.MM.YYYY` / `DD-MM-YYYY` / `D.M.YYYY`; worded `D <month-genitive> YYYY` with optional trailing `r.` (`12 stycznia 2024 r.`). Months: stycznia…grudnia (genitive).
- **Validation**: none. Numeric → 0.60; worded → 0.55.
- **Context words**: `data`, `dnia`, `z dnia`.
- **Metadata**: `{ kind: numeric|worded }`.
- **Limitation**: ranges, relative/uninflected forms out of scope (Constitution IX).

---

## Configured base (Presidio) recognizers

| Entity | Source | Notes |
|---|---|---|
| `PERSON` | spaCy `persName` (mapped, D2) | base score 0.85; no checksum |
| `LOCATION` | spaCy `placeName`/`geogName` (mapped, D2) | base 0.85; subsumed by address when contained |
| `EMAIL_ADDRESS` | Presidio `EmailRecognizer` | base ~0.80 |
| `PHONE_NUMBER` | Presidio `PhoneRecognizer(regions=["PL"])` | `phonenumbers`-backed; `+48`/`0048`/national |

PERSON/LOCATION require the NKJP→Presidio label mapping (research D2) or they detect nothing.
