"""T056 — anti-circularity guard (FR-002, Constitution I/II).

Ground truth must come ONLY from the gold standard. This test enforces, structurally,
that nothing under ``gateway_eval/scoring/`` imports ``gateway_api`` (which would let
the gateway's own output leak into scoring) and that no scorer reads the gateway's
``entities_replaced`` / session mappings as a reference. The only sanctioned
gateway_api imports live in ``corpus/synthetic_corpus_builder.py`` (corpus construction
only).
"""

from __future__ import annotations

import ast
from pathlib import Path

SCORING_DIR = Path(__file__).parent.parent / "gateway_eval" / "scoring"


def _imports(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_scoring_never_imports_gateway_api():
    offenders: list[str] = []
    for module_path in SCORING_DIR.glob("*.py"):
        for imported in _imports(module_path):
            if imported.startswith("gateway_api"):
                offenders.append(f"{module_path.name} imports {imported}")
    assert offenders == [], f"scoring must not import gateway_api: {offenders}"


def test_detection_scorers_never_use_gateway_entities_as_truth():
    """The detection-side scorers' reference is the gold standard only — they must
    not read the gateway's detected/replaced entities. (The leak audit is exempt: it
    may MASK the gateway's self-declared fake values to avoid miscounting them as
    leaks, but the gold original remains the sole leak oracle — D1/D4.)"""
    detection_scorers = (
        "detection_metrics.py",
        "span_alignment.py",
        "restoration_metrics.py",
    )
    for module_name in detection_scorers:
        source = (SCORING_DIR / module_name).read_text(encoding="utf-8")
        assert "entities_replaced" not in source, (
            f"{module_name} references entities_replaced — would be circular"
        )
