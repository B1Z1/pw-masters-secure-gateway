"""Per-type confidence thresholds with live reload (research D5).

Thresholds live in a dedicated YAML file, SEPARATE from the env-based ``Settings``
(spec clarification), and are read live: the parsed table is cached on the file's
mtime, so editing the file takes effect on the next request — no restart (FR-020).
No Redis dependency (the detect path stays stateless).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from .dto import DetectedEntity

logger = logging.getLogger("gateway_api")

_DEFAULT_PATH = Path(__file__).with_name("default_thresholds.yaml")
_BUILTIN = {"default": 0.30, "thresholds": {}}

_cache: dict | None = None
_cache_key: tuple[str, float] | None = None


def _clamp01(value: object, fallback: float = 0.30) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, v))


def _config_path() -> Path:
    override = os.environ.get("DETECTION_THRESHOLDS_PATH")
    return Path(override) if override else _DEFAULT_PATH


def _parse(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:  # missing/garbled → built-in defaults
        logger.warning(
            "threshold config unreadable (%s); using built-in defaults",
            type(exc).__name__,
        )
        return dict(_BUILTIN)
    default = _clamp01(data.get("default", 0.30))
    table: dict[str, float] = {}
    for key, value in (data.get("thresholds") or {}).items():
        table[str(key)] = _clamp01(value, fallback=default)
    return {"default": default, "thresholds": table}


def load_thresholds() -> dict:
    """Return ``{"default": float, "thresholds": {type: float}}`` with mtime reload."""
    global _cache, _cache_key
    path = _config_path()
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        return dict(_BUILTIN)
    if _cache is None or key != _cache_key:
        _cache = _parse(path)
        _cache_key = key
    return _cache


def threshold_for(entity_type: str) -> float:
    cfg = load_thresholds()
    return cfg["thresholds"].get(entity_type, cfg["default"])


def apply_thresholds(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Drop entities scoring below their per-type minimum (FR-019).

    Keep iff ``score >= threshold``. ``0.0`` keeps everything ("paranoid");
    ``1.0`` keeps nothing (scores are clamped to <= 0.99 → type disabled).
    """
    cfg = load_thresholds()
    table, default = cfg["thresholds"], cfg["default"]
    return [e for e in entities if e.score >= table.get(e.entity_type, default)]


def _reset_cache_for_tests() -> None:
    """Force a re-read on next access (used by tests that rewrite the file)."""
    global _cache, _cache_key
    _cache = None
    _cache_key = None
