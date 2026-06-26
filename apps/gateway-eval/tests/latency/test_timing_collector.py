"""T045 — latency bucketing, Stage 2 timing_ms parsing, percentile aggregation."""

from __future__ import annotations

from gateway_eval.latency.timing_collector import (
    aggregate_latency,
    bucket_label,
    make_sample,
    stage2_samples,
)

_EDGES = [500, 1500, 3000]
_ENTITY_EDGES = [5, 15, 30]


def test_bucket_label_boundaries():
    assert bucket_label(100, _EDGES) == "<500"
    assert bucket_label(500, _EDGES) == "500-1499"
    assert bucket_label(1500, _EDGES) == "1500-2999"
    assert bucket_label(5000, _EDGES) == ">=3000"


def test_make_sample_buckets():
    sample = make_sample(
        doc_id="d1",
        stage=1,
        channel="detect",
        ms=12.345678,
        doc_length=800,
        entity_count=7,
        length_edges=_EDGES,
        entity_count_edges=_ENTITY_EDGES,
    )
    assert sample.length_bucket == "500-1499"
    assert sample.entity_count_bucket == "5-14"
    assert sample.ms == 12.346


def test_stage2_samples_parse_known_channels():
    timing = {"ner_analysis": 2.0, "total": 5.0, "unknown_channel": 9.0}
    samples = stage2_samples(
        doc_id="d1",
        timing_ms=timing,
        doc_length=100,
        entity_count=2,
        length_edges=_EDGES,
        entity_count_edges=_ENTITY_EDGES,
    )
    channels = {s.channel for s in samples}
    assert channels == {"ner_analysis", "total"}  # unknown channel ignored
    assert all(s.stage == 2 for s in samples)


def test_aggregate_percentiles_single_and_multi():
    samples = [
        make_sample(doc_id=f"d{i}", stage=1, channel="detect", ms=float(i),
                    doc_length=100, entity_count=1, length_edges=_EDGES,
                    entity_count_edges=_ENTITY_EDGES)
        for i in (10, 20, 30)
    ]
    report = aggregate_latency(samples)
    stats = report.by_channel["detect"]
    assert stats.n == 3
    assert stats.mean == 20.0
    assert stats.p50 == 20.0
    assert "<500" in report.by_length_bucket
