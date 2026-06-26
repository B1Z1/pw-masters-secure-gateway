"""T032 — synthetic builder: checksum-valid IDs, exact offsets, reproducibility.

Requires the gateway-api package (FakeDataGenerator + checksums); skipped if its heavy
dependency chain (presidio/spaCy) is unavailable in the environment.
"""

from __future__ import annotations

import pytest

pytest.importorskip("gateway_api.pseudonym_generation")

from gateway_api.pii_detection.checksums import (  # noqa: E402
    nip_is_valid,
    nrb_is_valid,
    pesel_is_valid,
)

from gateway_eval.corpus.synthetic_corpus_builder import build_corpus  # noqa: E402


def test_offsets_are_exact():
    documents = build_corpus(seed=7, count=8)
    for document in documents:
        for entity in document.entities:
            assert document.text[entity.start : entity.end] == entity.text


def test_injected_identifiers_are_checksum_valid():
    documents = build_corpus(seed=7, count=12)
    checked = 0
    for document in documents:
        for entity in document.entities:
            digits = "".join(ch for ch in entity.text if ch.isdigit())
            if entity.type == "PESEL":
                assert pesel_is_valid(digits)
                checked += 1
            elif entity.type == "NIP":
                assert nip_is_valid(digits)
                checked += 1
            elif entity.type == "BANK_ACCOUNT":
                assert nrb_is_valid(digits)
                checked += 1
    assert checked > 0


def test_seeded_build_is_reproducible():
    first = build_corpus(seed=123, count=10)
    second = build_corpus(seed=123, count=10)
    assert [d.model_dump() for d in first] == [d.model_dump() for d in second]


def test_all_canonical_types_present_across_corpus():
    from gateway_eval.corpus.entity_vocabulary import CANONICAL_TYPES

    documents = build_corpus(seed=1, count=20)
    present = {e.type for d in documents for e in d.entities}
    assert set(CANONICAL_TYPES) <= present
