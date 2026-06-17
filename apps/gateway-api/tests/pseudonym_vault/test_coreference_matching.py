"""Coreference + bounded fuzzy matching (T034, research D7/D8)."""

from __future__ import annotations

from gateway_api.pseudonym_vault.coreference_matching import (
    aligned_fake,
    bounded_levenshtein,
    lemma_overlap,
)


def test_overlap_subset_matches():
    assert lemma_overlap("kowalski", "jan kowalski")
    assert lemma_overlap("jan kowalski", "kowalski")


def test_distinct_shared_root_does_not_match():
    # different surnames ("kowalska" vs "kowalski") share no whole token
    assert not lemma_overlap("anna kowalska", "jan kowalski")


def test_aligned_fake_projects_surname():
    assert aligned_fake("kowalski", "jan kowalski", "Marek Nowak") == "Nowak"


def test_aligned_fake_none_when_no_token_aligns():
    # hyphen-split part not a whole token of the stored name → no alignment
    out = aligned_fake("wąsowicz", "anna kowalczyk-wąsowicz", "Cezary Poleszak")
    assert out is None


def test_bounded_levenshtein_within_band():
    assert bounded_levenshtein("Nowaka", "Nowak") == 1
    assert bounded_levenshtein("Nowak", "Nowak") == 0


def test_bounded_levenshtein_exceeds_band():
    assert bounded_levenshtein("abcdef", "uvwxyz") is None
