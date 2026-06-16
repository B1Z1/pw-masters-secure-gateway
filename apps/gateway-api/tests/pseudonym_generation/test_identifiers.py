"""Identifier builders — all checksum-valid; PESEL gender; REGON variant (T013)."""

from __future__ import annotations

from gateway_api.pii_detection.checksums import (
    nip_is_valid,
    nrb_is_valid,
    pesel_gender,
    pesel_is_valid,
    regon9_is_valid,
    regon14_is_valid,
)
from gateway_api.pii_detection.dto import DetectedEntity
from gateway_api.pseudonym_generation import FakeDataGenerator


def _gen(entity_type, metadata=None, seed=1):
    e = DetectedEntity(
        entity_type=entity_type,
        start=0,
        end=1,
        score=1.0,
        text="x",
        metadata=metadata or {},
    )
    return FakeDataGenerator(seed=seed).generate(e)


def test_pesel_valid_and_gender_preserved():
    for gender in ("male", "female"):
        v = _gen("PESEL", {"gender": gender})
        assert pesel_is_valid(v.base)
        assert pesel_gender(v.base) == gender
        assert v.gender == gender


def test_pesel_post_2000_stays_valid_and_gendered():
    # Many seeds → some pick a 2000s birth year (month offset applied).
    for seed in range(30):
        v = _gen("PESEL", {"gender": "female"}, seed=seed)
        assert pesel_is_valid(v.base)
        assert pesel_gender(v.base) == "female"


def test_nip_valid_leading_zero_allowed():
    for seed in range(15):
        assert nip_is_valid(_gen("NIP", seed=seed).base)


def test_regon_variant_preserved():
    v9 = _gen("REGON", {"variant": "9"})
    assert len(v9.base) == 9 and regon9_is_valid(v9.base)
    v14 = _gen("REGON", {"variant": "14"})
    assert len(v14.base) == 14 and regon14_is_valid(v14.base)


def test_bank_account_mod97():
    for seed in range(15):
        v = _gen("POLISH_BANK_ACCOUNT", seed=seed)
        assert len(v.base) == 26 and nrb_is_valid(v.base)
