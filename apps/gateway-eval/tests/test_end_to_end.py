"""T026/T046 — end-to-end harness runs against the in-process FakeGateway.

Hermetic (no network, Redis, or spaCy): the FakeGateway mimics a well-behaved gateway
built from the gold corpus, while the harness still scores its outputs independently
against gold. Asserts a complete report is produced and that metrics are reproducible.
"""

from __future__ import annotations

from pathlib import Path

from gateway_eval.config import EvaluationConfig
from gateway_eval.run_evaluation import EXIT_OK, run_evaluation


def _config(sample_corpus_path: Path, tmp_path: Path, stage: str = "1") -> EvaluationConfig:
    return EvaluationConfig(
        base_url="http://test",
        corpus_path=sample_corpus_path.parent,
        real_corpus_path=tmp_path / "no-real",
        out_dir=tmp_path / "out",
        results_dir=tmp_path / "results",
        stage=stage,
    )


async def test_stage1_produces_complete_report(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = _config(sample_corpus_path, tmp_path)
    result = await run_evaluation(config, client=fake_gateway_factory())

    assert result.exit_code == EXIT_OK
    aggregate = result.aggregate
    assert aggregate is not None
    assert aggregate.corpus_stats.n_docs == 6
    # The fake gateway detects every gold span → perfect recall under overlap.
    assert aggregate.detection_overlap.micro.recall == 1.0
    # It restores every original exactly at position.
    assert aggregate.restoration.doc_exact_restore_rate == 1.0
    assert aggregate.latency.by_channel  # wall-clock samples recorded


async def test_metrics_are_reproducible(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = _config(sample_corpus_path, tmp_path)
    first = await run_evaluation(config, client=fake_gateway_factory())
    second = await run_evaluation(config, client=fake_gateway_factory())

    assert (
        first.aggregate.detection_overlap.model_dump()
        == second.aggregate.detection_overlap.model_dump()
    )
    assert (
        first.aggregate.restoration.model_dump()
        == second.aggregate.restoration.model_dump()
    )


async def test_both_stages_complete_report(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = _config(sample_corpus_path, tmp_path, stage="both")
    result = await run_evaluation(config, client=fake_gateway_factory())

    assert result.exit_code == EXIT_OK
    aggregate = result.aggregate
    assert aggregate.stage2_summary == {
        "n_docs": 6,
        "n_leak_free": 6,
        "n_answer_restored": 6,
    }
    # Stage 2 timing_ms channels show up in the latency report.
    assert "total" in aggregate.latency.by_channel


async def test_stage2_only_skips_detection(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = _config(sample_corpus_path, tmp_path, stage="2")
    result = await run_evaluation(config, client=fake_gateway_factory())

    assert result.exit_code == EXIT_OK
    assert result.aggregate.detection_overlap is None
    assert result.aggregate.stage2_summary["n_leak_free"] == 6


async def test_missed_type_lowers_recall(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = _config(sample_corpus_path, tmp_path)
    gateway = fake_gateway_factory(miss_types=frozenset({"PESEL"}))
    result = await run_evaluation(config, client=gateway)

    pesel = next(
        m for m in result.aggregate.detection_overlap.per_type if m.type == "PESEL"
    )
    assert pesel.recall == 0.0
    assert pesel.fn > 0
