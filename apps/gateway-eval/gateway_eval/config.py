"""Evaluation run configuration (data-model.md §8).

A single ``EvaluationConfig`` carries everything a run needs: where the gateway is,
where the corpus lives, where artifacts go, the seed, the span-matching policy, and
the latency bucket thresholds. No secrets — the harness needs none (no auth, Echo
provider, offline).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

# Repo-root-relative defaults resolved lazily against the current working directory
# of the run (the Nx target sets cwd to the project root).
_DEFAULT_SYNTHETIC_CORPUS = "gateway_eval/corpus/data/synthetic"
_DEFAULT_REAL_CORPUS = "gateway_eval/corpus/data/real"


class EvaluationConfig(BaseModel):
    """Inputs for one ``evaluate`` (or ``build-corpus``) invocation."""

    base_url: str = "http://localhost:8000"
    corpus_path: Path = Path(_DEFAULT_SYNTHETIC_CORPUS)
    real_corpus_path: Path = Path(_DEFAULT_REAL_CORPUS)
    out_dir: Path = Path("../../thesis/images")
    results_dir: Path = Path("eval-results")
    stage: str = "both"  # "1" | "2" | "both"
    provider: str = "echo"
    seed: int = 42
    strict_spans: bool = False
    request_timeout_s: float = 30.0
    max_retries: int = 2

    # Latency buckets (data-model §6). Upper-exclusive character / entity-count edges.
    length_buckets: list[int] = Field(default_factory=lambda: [500, 1500, 3000])
    entity_count_buckets: list[int] = Field(default_factory=lambda: [5, 15, 30])

    @property
    def stage_one_enabled(self) -> bool:
        return self.stage in ("1", "both")

    @property
    def stage_two_enabled(self) -> bool:
        return self.stage in ("2", "both")

    @property
    def echo_model(self) -> str:
        """The chat ``model`` that routes to the deterministic Echo provider."""
        return f"{self.provider}/{self.provider}"
