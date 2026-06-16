# Contract — Fake-data generators (`gateway_api/pseudonym_generation/`)

`FakeDataGenerator.generate(entity: DetectedEntity) -> FakeValue` dispatches on `entity.entity_type` to a
per-type builder. Built on **Faker(`pl_PL`)** (Constitution VII). **Stateless** and **deterministic with an
injectable seed** (`FakeDataGenerator(seed=...)`) so tests are reproducible; production uses a random seed.
Collision avoidance is the `MappingStore`'s job (research D6) — builders just produce one valid value.
Abstract placeholder tokens are forbidden.

## Per-type builder contracts

| entity_type | Builder output (`FakeValue`) | Validity rule (test target) |
|---|---|---|
| `PERSON` | `base` = "First Last" (one gender); `forms` from inflection; `gender` set | first+last same gender; surname **post-filtered to a declinable pattern** (re-roll until `classify` ≠ INDECLINABLE for the prototype's clean cases); ≠ original |
| `LOCATION` | `base` = city; `forms` from inflection (city pattern) | realistic Polish city; declinable city pattern preferred |
| `ADDRESS` | `base` = "ul. … N, NN-NNN City"; `forms = None` | atomic; street + postcode `NN-NNN` + city; never inflected |
| `EMAIL_ADDRESS` | `base` = realistic Polish e-mail | valid email shape; ASCII local part |
| `PHONE_NUMBER` | `base` = Polish phone | valid PL format (9 national digits, optional `+48`/spaces) |
| `DATE_TIME` | `base` = `DD.MM.YYYY` | within **±10 years** of the parsed original (research D9); valid calendar date |
| `PESEL` | `base` = 11-digit PESEL | `pesel_is_valid`; `pesel_gender(fake) == entity.metadata["gender"]`; post-2000 month offset handled; ≠ original |
| `NIP` | `base` = 10-digit NIP | `nip_is_valid` (leading 0 allowed) |
| `REGON` | `base` = 9- or 14-digit REGON | `regon9_is_valid` / `regon14_is_valid`; **variant = `entity.metadata["variant"]` preserved** |
| `POLISH_BANK_ACCOUNT` | `base` = 26-digit NRB (formatting per detection) | `nrb_is_valid` (mod-97) |

Unknown/unsupported types: return the original text unchanged (no mapping) — defensive, logged as a count
only.

## Checksum generation helpers (`pii_detection/checksums.py`, additive)

Reuse Epic 2's weight tuples; add generators that emit a valid control digit, then assert via the existing
`*_is_valid` (belt-and-braces in tests):
- `pesel_control_digit(d10) -> int`, plus a `make_pesel(birth_date, gender, serial) -> str` helper.
- `nip_control_digit(d9) -> int`; `regon9_control_digit(d8)`, `regon14_control_digit(d13)`.
- `nrb_check_digits(bban) -> str` (two leading digits so mod-97 == 1).

These live with the other pure checksum logic so generation and validation share one source of truth.

## Collision fallback (applied by `MappingStore`, research D6)

| Type group | On 3 collisions |
|---|---|
| PESEL/NIP/REGON/bank/phone/email | deterministic uniquification (re-roll digits / numeric suffix before `@`) |
| PERSON/LOCATION | **re-roll** a new realistic value — never a numeric suffix (Constitution VII) |
| DATE_TIME/ADDRESS | re-roll within the same constraints |

## Determinism

`generate` is a pure function of `(entity, seed)`. `test_generator.py` asserts identical output for a fixed
seed; per-type tests assert validity invariants above and the ±10y / gender / variant rules.
