"""All result/report data shapes — the on-disk JSON schema (data-model.md §5/§7).

Every report type lives here once; ``scoring/`` and ``latency/`` import these and hold
only the computation logic (one-way dependency, no import cycles — analysis M1). The
publishable ``AggregateResult`` carries only counts/metrics (no originals);
``PerDocumentResult`` may embed originals and is therefore treated as sensitive.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SpanPolicy = Literal["overlap", "exact"]
RestorationOutcome = Literal[
    "exact", "correct_inflection", "fuzzy_recovered", "base_form_only", "missed"
]
LeakMatchMode = Literal["exact", "exact_id", "stem", "diacritic_fold"]


# --- detection -------------------------------------------------------------


class TypeMetrics(BaseModel):
    type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0  # gold count for this type


class ConfusionMatrix(BaseModel):
    labels: list[str]  # CANONICAL_TYPES + ["MISS", "SPURIOUS"]
    matrix: list[list[int]]  # rows = gold label, cols = predicted label


class DetectionReport(BaseModel):
    policy: SpanPolicy
    per_type: list[TypeMetrics]
    micro: TypeMetrics
    macro: TypeMetrics
    confusion_matrix: ConfusionMatrix
    unmapped_labels: dict[str, int] = Field(default_factory=dict)


# --- leak audit ------------------------------------------------------------


class LeakFinding(BaseModel):
    doc_id: str
    type: str
    original: str
    form_found: str
    start: int
    end: int
    match_mode: LeakMatchMode


class LeakReport(BaseModel):
    total_leaks: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_doc: dict[str, int] = Field(default_factory=dict)
    findings: list[LeakFinding] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total_leaks == 0


# --- restoration -----------------------------------------------------------


class RestorationDetail(BaseModel):
    doc_id: str
    type: str
    original: str
    outcome: RestorationOutcome
    restored_surface: str | None = None
    position_correct: bool = False


class RestorationReport(BaseModel):
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    doc_exact_restore_rate: float = 0.0


# --- latency ---------------------------------------------------------------


class LatencySample(BaseModel):
    doc_id: str
    stage: int
    channel: str
    ms: float
    length_bucket: str
    entity_count_bucket: str


class ChannelStats(BaseModel):
    p50: float = 0.0
    p90: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    n: int = 0


class LatencyReport(BaseModel):
    by_channel: dict[str, ChannelStats] = Field(default_factory=dict)
    by_length_bucket: dict[str, dict[str, ChannelStats]] = Field(default_factory=dict)
    by_entity_bucket: dict[str, dict[str, ChannelStats]] = Field(default_factory=dict)


# --- run + per-document + aggregate ---------------------------------------


class RunConfigSnapshot(BaseModel):
    seed: int
    base_url: str
    gateway_health: dict
    corpus_version_hash: str
    span_policy: SpanPolicy
    provider: str
    started_at: str
    finished_at: str
    gateway_eval_version: str = "1.0.0"


class Stage2Result(BaseModel):
    leak_free: bool
    answer_restored: bool
    timing_ms: dict[str, float] = Field(default_factory=dict)


class PerDocumentResult(BaseModel):
    """May embed originals (synthetic or real) — sensitive for ``source="real"``."""

    doc_id: str
    source: str
    contract_type: str
    n_gold_entities: int
    detection_overlap: DetectionReport | None = None
    detection_exact: DetectionReport | None = None
    false_negatives: list[str] = Field(
        default_factory=list
    )  # "TYPE: surface" (overlap)
    false_positives: list[str] = Field(default_factory=list)  # "TYPE@start" (overlap)
    leaks: list[LeakFinding] = Field(default_factory=list)
    restoration: list[RestorationDetail] = Field(default_factory=list)
    latency: list[LatencySample] = Field(default_factory=list)
    stage2: Stage2Result | None = None
    errors: list[str] = Field(default_factory=list)


class CorpusStats(BaseModel):
    n_docs: int
    n_entities: int
    by_type: dict[str, int]
    by_source: dict[str, int]
    synthetic_ratio: float
    all_types_present: bool


class AggregateResult(BaseModel):
    """Publishable summary — counts/metrics only, no originals (FR-032)."""

    config: RunConfigSnapshot
    corpus_stats: CorpusStats
    detection_overlap: DetectionReport | None = None
    detection_exact: DetectionReport | None = None
    leak: LeakReport | None = None
    restoration: RestorationReport | None = None
    latency: LatencyReport | None = None
    stage2_summary: dict | None = None
