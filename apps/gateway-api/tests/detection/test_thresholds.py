"""Threshold post-filter & live-reload tests (T035, FR-019/FR-020/FR-022)."""

from __future__ import annotations

import os

from gateway_api.detection.dto import DetectedEntity
from gateway_api.detection.thresholds import apply_thresholds, load_thresholds


def _ent(entity_type: str, score: float) -> DetectedEntity:
    return DetectedEntity(
        entity_type=entity_type, start=0, end=1, score=score, text="x"
    )


def test_default_thresholds_loaded():
    cfg = load_thresholds()
    assert cfg["thresholds"]["PESEL"] == 0.25
    assert cfg["default"] == 0.30


def test_keeps_at_or_above_threshold():
    kept = apply_thresholds([_ent("PESEL", 0.25), _ent("PESEL", 0.24)])
    assert [e.score for e in kept] == [0.25]


def test_unknown_type_uses_default():
    # default 0.30: 0.31 kept, 0.29 dropped.
    kept = apply_thresholds([_ent("MYSTERY", 0.31), _ent("MYSTERY", 0.29)])
    assert [e.score for e in kept] == [0.31]


def test_paranoid_zero_surfaces_everything(thresholds_file):
    thresholds_file("default: 0.30\nthresholds:\n  PESEL: 0.0\n")
    kept = apply_thresholds([_ent("PESEL", 0.0), _ent("PESEL", 0.01)])
    assert len(kept) == 2


def test_disable_one_drops_everything(thresholds_file):
    thresholds_file("default: 0.30\nthresholds:\n  PESEL: 1.0\n")
    # Even the ceiling score (0.99) is below 1.0 -> type disabled.
    kept = apply_thresholds([_ent("PESEL", 0.99)])
    assert kept == []


def test_live_reload_without_restart(thresholds_file):
    path = thresholds_file("default: 0.30\nthresholds:\n  PESEL: 0.0\n")
    assert apply_thresholds([_ent("PESEL", 0.1)]) != []  # surfaced

    # Rewrite the same file and bump mtime — no reset, no restart.
    path.write_text("default: 0.30\nthresholds:\n  PESEL: 1.0\n", encoding="utf-8")
    st = path.stat()
    os.utime(path, (st.st_atime + 10, st.st_mtime + 10))

    assert apply_thresholds([_ent("PESEL", 0.99)]) == []  # now disabled
