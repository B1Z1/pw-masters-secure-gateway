# Quickstart — Validating the Readability Refactor

How to prove the refactor is **behavior-preserving** and the readability goals are met. Run from the
backend project root unless noted:

```bash
cd apps/gateway-api
```

All commands assume `uv` (see `.python-version`, `pyproject.toml`). Nx equivalents from repo root are
given where useful (`nx <target> gateway-api`).

## Prerequisites

- Python 3.12 + `uv` with dev deps synced (`uv sync` / `nx sync gateway-api`).
- For the end-to-end step only: Redis reachable and a valid base64 `REDIS_ENCRYPTION_KEY` (Epic 1
  gate). Unit tests need **no** Redis — they use `fakeredis`.

## 1. Lint & format (style gate)

```bash
uv run ruff check gateway_api tests          # nx lint gateway-api   — rules E/F/UP/B/SIM/I
uv run ruff format --check gateway_api tests # nx format gateway-api — line length 88
```

**Expected**: clean. (Note: ruff does not enforce the *naming* convention — `pep8-naming` is not
enabled — so steps 4–5 below cover that by hand.)

## 2. Full test suite (behavior oracle — the core check)

```bash
uv run pytest tests/                          # nx test gateway-api
```

**Expected**: same pass/skip counts as before the refactor, with **no edits to any assertion** —
only updated import paths and renamed test files. The vault tests specifically protect the logic
that the decomposition moves around:

```bash
uv run pytest tests/pseudonym_vault/ -v
```

Key cases that must stay green:
- `test_full_name_then_surname_only`, `test_distinct_people_shared_root`,
  `test_ambiguous_surname_becomes_new_person` → `CoreferenceResolver` extraction is correct.
- `test_collision_free` → `UniqueFakeFactory` preserves collision retry + fallback.
- `test_restore_round_trip_with_inflection`, `test_round_trip_exact_for_female_consonant_surname`,
  `test_listing_includes_entity_seen_only_in_oblique_case` → `OriginalSurfaceRestorer` is faithful.
- `test_encrypted_at_rest_no_pii_in_names_or_values` → Constitution III/VIII hold through the
  `EncryptedJsonCodec` + `SessionMappingRepository` split (no PII in field names or values).
- `test_ttl_set_and_sliding`, `test_delete_removes_all`, `test_get_all_mappings_lists_pairs`.

## 3. Renamed files & imports resolve

```bash
# the 5 renamed modules exist; the old names are gone
ls gateway_api/pseudonym_vault/{aes_gcm_encryption,session_layout,mapping_keys,coreference_matching,session_mapping_repository,unique_fake_factory,original_restoration,mapping_store}.py
! ls gateway_api/pseudonym_vault/{store,encryption,matching,keys,session}.py 2>/dev/null

# every import site updated (8 files): no stale references remain
! grep -rn "pseudonym_vault\.\(store\|encryption\|matching\|keys\|session\)\b\|from \.\(store\|encryption\|matching\|keys\|session\)\b" gateway_api tests

# app imports cleanly
uv run python -c "import gateway_api.main"
```

**Expected**: the eight renamed/new files exist, the five old names are absent, and no stale import
strings remain in `gateway_api/` or `tests/` (sites: `pseudonym_vault/__init__.py`,
`api/pseudonymize.py`, `tests/conftest.py`, `tests/pseudonym_vault/{test_encryption,test_keys,test_matching,test_store}.py`).

## 4. No leftover abbreviations (readability gate)

Run across the **whole package** — FR-010 / SC-002 cover all of `gateway_api/`, not just the vault:

```bash
grep -rnE "\b(hkey|mkey|fwd|_enc|_gen|blob|rec|ob|cset|sset|idxs|fmap)\b" gateway_api/
grep -rnE "\bfor [a-z] in\b" gateway_api/   # single-letter loop vars, any package
```

**Expected**: no hits anywhere under `gateway_api/` (domain acronyms like `pii`, `nip`, `hmac`,
`ttl`, `aes` are allowed and won't match the list above). The alternation is illustrative — each
package may surface its own shorthands (e.g. recognizer/builder locals); extend it with any
abbreviations found while cleaning `pii_detection/`, `pseudonym_generation/`, `api/`, and the
top-level modules until the grep is clean package-wide.

## 5. Comments justify *why*, not *what*

Spot-check any refactored module: comments that merely restated the next line are gone; remaining
comments explain rationale (research references, constitution notes). This is a manual review
matching SC-005.

## 6. Agent rule is present and auto-loads

```bash
ls .claude/rules/python-naming-conventions.md          # from repo root
head -5 .claude/rules/python-naming-conventions.md      # YAML frontmatter with paths:
```

Then, in a Claude Code session working on a backend file, run `/memory` and confirm
`python-naming-conventions.md` appears in the loaded rules list (SC-006). The frontmatter
`paths: ["apps/gateway-api/**/*.py"]` scopes it so it loads only for backend Python.

## 7. End-to-end round-trip (needs Redis)

Using the EPIC 3 example (`specs/003-fake-data-generator/quickstart.md`): `POST /v1/pseudonymize`
with Polish text containing PII, then `POST /v1/depseudonymize` with the returned
`pseudonymized_text` + `session_id`.

**Expected**: the restored text equals the original (case-aware for PERSON/LOCATION) — identical to
pre-refactor behavior. Confirms the facade orchestration is wired correctly across the new modules.

## 8. All services start cleanly (full-stack smoke test) — final gate

Confirm the refactor didn't break startup of any service. **Preferred**: run the `/debug-services`
skill — it knows this project's exact commands for the three services (Redis, gateway-api,
gateway-ui) and the `/health` checks. Representative manual equivalent (from repo root):

```bash
docker compose up -d --build            # see /debug-services for authoritative commands
docker compose ps                        # every service Up / healthy
curl -fsS http://localhost:8000/health   # aggregate health: expect healthy, not degraded
```

**Expected**: all services start without errors and aggregate `/health` reports healthy (no degraded
status, no unavailable service) — SC-008 / FR-011. Any startup failure or degraded status is a
refactor regression; invoke `/debug-services` to diagnose.

> Note: image builds in this environment require the Netskope CA — pass
> `CA_CERT_FILE=~/.certs/netskope-ca.pem` to the build.

---

**Done when**: steps 1–3 pass (behavior + structure), step 4 is clean (readability), steps 5–6 are
reviewed (self-documentation + rule), step 7 round-trips (end-to-end), and step 8 confirms all
services start healthy. Detailed task breakdown: run `/speckit-tasks`.
