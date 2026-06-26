"""Latency collection + bucketing (FR-027/FR-028, research D5).

Two channels, never mixed: Stage 1 wall-clock per endpoint (measured client-side) and
Stage 2 per-stage ``timing_ms`` (self-reported by the gateway). Samples are bucketed
by document length (characters) and gold entity count so the thesis can show scaling.
"""

from __future__ import annotations

from ..reporting.result_models import ChannelStats, LatencyReport, LatencySample

# Stage 2 keys from anonymization_meta.timing_ms (gateway TimingBreakdown).
STAGE2_CHANNELS = (
    "ner_analysis",
    "fake_generation",
    "redis_write",
    "llm_request",
    "deanonymization",
    "total",
)


def bucket_label(value: int, edges: list[int]) -> str:
    """Upper-exclusive bucket label for a value given ascending edges."""
    previous = 0
    for edge in edges:
        if value < edge:
            return f"{previous}-{edge - 1}" if previous else f"<{edge}"
        previous = edge
    return f">={previous}"


def make_sample(
    *,
    doc_id: str,
    stage: int,
    channel: str,
    ms: float,
    doc_length: int,
    entity_count: int,
    length_edges: list[int],
    entity_count_edges: list[int],
) -> LatencySample:
    return LatencySample(
        doc_id=doc_id,
        stage=stage,
        channel=channel,
        ms=round(ms, 3),
        length_bucket=bucket_label(doc_length, length_edges),
        entity_count_bucket=bucket_label(entity_count, entity_count_edges),
    )


def stage2_samples(
    *,
    doc_id: str,
    timing_ms: dict[str, float],
    doc_length: int,
    entity_count: int,
    length_edges: list[int],
    entity_count_edges: list[int],
) -> list[LatencySample]:
    samples: list[LatencySample] = []
    for channel in STAGE2_CHANNELS:
        if channel in timing_ms:
            samples.append(
                make_sample(
                    doc_id=doc_id,
                    stage=2,
                    channel=channel,
                    ms=float(timing_ms[channel]),
                    doc_length=doc_length,
                    entity_count=entity_count,
                    length_edges=length_edges,
                    entity_count_edges=entity_count_edges,
                )
            )
    return samples


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    interpolation = position - lower
    value = (
        sorted_values[lower] * (1 - interpolation)
        + sorted_values[upper] * interpolation
    )
    return round(value, 3)


def _stats(values: list[float]) -> ChannelStats:
    if not values:
        return ChannelStats()
    ordered = sorted(values)
    return ChannelStats(
        p50=_percentile(ordered, 0.50),
        p90=_percentile(ordered, 0.90),
        p99=_percentile(ordered, 0.99),
        mean=round(sum(ordered) / len(ordered), 3),
        n=len(ordered),
    )


def _group(samples: list[LatencySample], key) -> dict[str, dict[str, ChannelStats]]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for sample in samples:
        grouped.setdefault(key(sample), {}).setdefault(sample.channel, []).append(
            sample.ms
        )
    return {
        bucket: {channel: _stats(values) for channel, values in channels.items()}
        for bucket, channels in grouped.items()
    }


def aggregate_latency(samples: list[LatencySample]) -> LatencyReport:
    by_channel_values: dict[str, list[float]] = {}
    for sample in samples:
        by_channel_values.setdefault(sample.channel, []).append(sample.ms)
    return LatencyReport(
        by_channel={
            channel: _stats(values) for channel, values in by_channel_values.items()
        },
        by_length_bucket=_group(samples, lambda sample: sample.length_bucket),
        by_entity_bucket=_group(samples, lambda sample: sample.entity_count_bucket),
    )
