"""T051 — reporting: figures render, Typst tables written, real originals redacted."""

from __future__ import annotations

from gateway_eval.config import EvaluationConfig
from gateway_eval.reporting import error_analysis, figures, tables
from gateway_eval.reporting.result_models import (
    AggregateResult,
    CorpusStats,
    LeakFinding,
    LeakReport,
    PerDocumentResult,
    RunConfigSnapshot,
)
from gateway_eval.run_evaluation import run_evaluation


async def test_figures_render_png_and_svg(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = EvaluationConfig(
        base_url="http://test",
        corpus_path=sample_corpus_path.parent,
        real_corpus_path=tmp_path / "no-real",
        stage="both",
    )
    result = await run_evaluation(config, client=fake_gateway_factory())
    out = tmp_path / "images"
    written = figures.render_all(result.aggregate, out)

    for stem in ("confusion_matrix", "prf1_by_type", "restoration_outcomes", "latency_distribution"):
        assert (out / f"{stem}.png").exists()
        assert (out / f"{stem}.svg").exists()
    assert written


async def test_typst_tables_written(
    fake_gateway_factory, sample_corpus_path, tmp_path
):
    config = EvaluationConfig(
        base_url="http://test",
        corpus_path=sample_corpus_path.parent,
        real_corpus_path=tmp_path / "no-real",
        stage="both",
    )
    result = await run_evaluation(config, client=fake_gateway_factory())
    out = tmp_path / "images"
    tables.write_typst_tables(result.aggregate, out)

    detection = (out / "detection_by_type.typ").read_text(encoding="utf-8")
    assert "#table(" in detection
    assert (out / "restoration_outcomes.typ").exists()
    assert (out / "latency_summary.typ").exists()


def test_error_analysis_redacts_real_source_originals(tmp_path):
    leak = LeakFinding(
        doc_id="real-001",
        type="PERSON",
        original="Jan Kowalski",
        form_found="Kowalskiego",
        start=0,
        end=12,
        match_mode="stem",
    )
    per_document = [
        PerDocumentResult(
            doc_id="real-001",
            source="real",
            contract_type="najem",
            n_gold_entities=1,
            false_negatives=["PERSON: Jan Kowalski"],
            leaks=[leak],
        )
    ]
    aggregate = AggregateResult(
        config=RunConfigSnapshot(
            seed=42,
            base_url="http://test",
            gateway_health={"status": "ok"},
            corpus_version_hash="abc",
            span_policy="overlap",
            provider="echo",
            started_at="t0",
            finished_at="t1",
        ),
        corpus_stats=CorpusStats(
            n_docs=1, n_entities=1, by_type={"PERSON": 1},
            by_source={"real": 1, "synthetic": 0}, synthetic_ratio=0.0,
            all_types_present=False,
        ),
        leak=LeakReport(total_leaks=1, findings=[leak]),
    )
    path = error_analysis.write_report(aggregate, per_document, tmp_path / "images")
    text = path.read_text(encoding="utf-8")
    assert "Jan Kowalski" not in text  # real original never published
    assert "[REDACTED]" in text
    assert "real-001" in text
