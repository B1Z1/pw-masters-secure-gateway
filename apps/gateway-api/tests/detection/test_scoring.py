"""Scoring band tests (T034, FR-015/FR-016/FR-022, research D6)."""

from __future__ import annotations

from gateway_api.detection import scoring


def test_clamp_ceiling():
    assert scoring.clamp_score(1.0) == 0.99
    assert scoring.clamp_score(1.5) == 0.99


def test_clamp_floor():
    assert scoring.clamp_score(-0.2) == 0.0


def test_clamp_passthrough():
    assert scoring.clamp_score(0.5) == 0.5


def test_valid_beats_invalid():
    assert scoring.S_VALID > scoring.S_INVALID


def test_valid_plus_context_clamps_to_ceiling():
    # 0.80 + 0.20 = 1.0 -> clamped to 0.99 (the "valid + labelled" band).
    assert (
        scoring.clamp_score(scoring.S_VALID + scoring.CONTEXT_SIMILARITY_FACTOR) == 0.99
    )


def test_ceiling_below_disable_threshold():
    # A configured threshold of 1.0 must disable a type: ceiling < 1.0.
    assert scoring.SCORE_CEILING < 1.0


def test_context_floor_disabled():
    # min_score floor is 0 so a label near a bad-checksum value only adds the
    # fixed bonus (keeps bands monotonic).
    assert scoring.CONTEXT_MIN_SCORE == 0.0
