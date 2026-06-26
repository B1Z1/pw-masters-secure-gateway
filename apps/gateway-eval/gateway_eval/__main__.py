"""gateway-eval CLI (contracts/cli.md). Built with typer.

``evaluate`` drives the live gateway and writes all artifacts; ``build-corpus``
(re)generates the seeded synthetic corpus offline. Exit codes: 0 ok / zero leaks,
1 leak audit failed, 2 cannot run (degraded gateway or bad corpus), 3 usage error.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import EvaluationConfig
from .reporting import results_writer
from .run_evaluation import RunResult, run_evaluation

app = typer.Typer(add_completion=False, help="Gateway PII evaluation harness (EPIC 8).")


@app.command()
def evaluate(
    base_url: str = typer.Option(
        "http://localhost:8000", help="Live gateway base URL."
    ),
    corpus: Path = typer.Option(
        Path("gateway_eval/corpus/data/synthetic"), help="Synthetic corpus directory."
    ),
    real_corpus: Path = typer.Option(
        Path("gateway_eval/corpus/data/real"),
        help="Real corpus directory (local only).",
    ),
    out: Path = typer.Option(
        Path("../../thesis/images"), help="Publishable artifacts dir."
    ),
    results: Path = typer.Option(
        Path("eval-results"), help="Machine-readable results dir."
    ),
    stage: str = typer.Option("both", help="Which stage(s) to run: 1 | 2 | both."),
    provider: str = typer.Option("echo", help="Stage 2 provider (maps to echo/echo)."),
    strict_spans: bool = typer.Option(
        False, help="Make exact-span the headline metric."
    ),
    timeout: float = typer.Option(30.0, help="Per-request timeout (seconds)."),
) -> None:
    if stage not in ("1", "2", "both"):
        typer.echo(f"invalid --stage {stage!r} (use 1|2|both)", err=True)
        raise typer.Exit(code=3)

    config = EvaluationConfig(
        base_url=base_url,
        corpus_path=corpus,
        real_corpus_path=real_corpus,
        out_dir=out,
        results_dir=results,
        stage=stage,
        provider=provider,
        strict_spans=strict_spans,
        request_timeout_s=timeout,
    )

    result = asyncio.run(run_evaluation(config))
    _print_summary(result, config)

    if result.aggregate is not None:
        written = results_writer.write_all(
            config.results_dir, result.aggregate, result.per_document
        )
        _maybe_write_reports(result, config)
        typer.echo(
            f"wrote {len(written)} machine-readable file(s) to {config.results_dir}"
        )

    raise typer.Exit(code=result.exit_code)


@app.command("build-corpus")
def build_corpus(
    seed: int = typer.Option(42, help="Faker + selection seed (reproducible)."),
    corpus_out: Path = typer.Option(
        Path("gateway_eval/corpus/data/synthetic"),
        help="Where the gold JSONL is written.",
    ),
    count: int = typer.Option(56, help="Number of synthetic documents to generate."),
) -> None:
    # Lazy import: the builder pulls gateway_api (FakeDataGenerator + checksums), which
    # is heavy — keep it out of the module import path.
    from .corpus.synthetic_corpus_builder import build_and_write

    documents = build_and_write(seed=seed, out_dir=corpus_out, count=count)
    typer.echo(
        f"built {len(documents)} synthetic documents (seed={seed}) into {corpus_out}"
    )


def _print_summary(result: RunResult, config: EvaluationConfig) -> None:
    for message in result.messages:
        typer.echo(f"warning: {message}", err=True)
    if result.aggregate is None:
        typer.echo("evaluation did not run — see warnings above.", err=True)
        return

    aggregate = result.aggregate
    stats = aggregate.corpus_stats
    typer.echo(
        f"corpus: {stats.n_docs} docs, {stats.n_entities} entities, "
        f"synthetic_ratio={stats.synthetic_ratio}, all_types={stats.all_types_present}"
    )
    headline = (
        aggregate.detection_exact
        if config.strict_spans
        else aggregate.detection_overlap
    )
    if headline is not None:
        policy = "exact" if config.strict_spans else "overlap"
        typer.echo(
            f"detection [{policy}] — recall(micro)={headline.micro.recall} "
            f"precision(micro)={headline.micro.precision} f1(micro)={headline.micro.f1} "
            f"| recall(macro)={headline.macro.recall}"
        )
    if aggregate.leak is not None:
        verdict = "PASS" if aggregate.leak.passed else "FAIL"
        typer.echo(f"leak audit: {aggregate.leak.total_leaks} leak(s) — {verdict}")
    if aggregate.restoration is not None:
        typer.echo(
            f"restoration: doc_exact_restore_rate={aggregate.restoration.doc_exact_restore_rate} "
            f"outcomes={aggregate.restoration.by_outcome}"
        )
    if aggregate.stage2_summary is not None:
        typer.echo(f"stage2: {aggregate.stage2_summary}")


def _maybe_write_reports(result: RunResult, config: EvaluationConfig) -> None:
    """Render figures + Typst tables + error analysis when those modules are present
    (US5). Imported lazily so Stage-1-only runs work before reporting lands."""
    try:
        from .reporting import error_analysis, figures, tables
    except ImportError:
        return
    if result.aggregate is None:
        return
    figures.render_all(result.aggregate, config.out_dir)
    tables.write_typst_tables(result.aggregate, config.out_dir)
    error_analysis.write_report(result.aggregate, result.per_document, config.out_dir)


if __name__ == "__main__":
    app()
