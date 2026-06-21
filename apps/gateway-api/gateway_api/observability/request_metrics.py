"""Request-scoped metrics for the chat round-trip (Epic 6, FR-014/FR-015, D4/D11).

``RequestMetrics`` lives on ``request.state`` so the chat endpoint can fill the
per-stage timing + per-type entity counts, and the logging middleware can read
and emit them as ONE structured JSON line. The inbound stages (``ner_analysis``,
``fake_generation``, ``redis_write``) are attributed via a ``contextvars``
accumulator the pipeline activates around inbound persistence — so the store/
repository contribute their timings without any public signature change, and
outbound work (de-pseudonymization) is never counted as ``redis_write``.

Naming note: the system performs *pseudonymization*; the field names
``deanonymization`` / ``anonymization_*`` are the fixed frontend-contract keys
(they pre-date this epic — see ``AnonymizationPipeline``), not a different
operation. Do not rename them.
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from dataclasses import dataclass, field

# Active inbound stage accumulator (stage name → elapsed seconds). ``None`` when
# no inbound capture is in progress: every ``record`` below is then a no-op, so
# the debug endpoints and metric-free tests pay nothing.
_inbound_stage_seconds: contextvars.ContextVar[dict[str, float] | None] = (
    contextvars.ContextVar("inbound_stage_seconds", default=None)
)


def record_inbound_stage_seconds(stage: str, seconds: float) -> None:
    """Add ``seconds`` to the active inbound accumulator for ``stage`` (or no-op)."""
    accumulator = _inbound_stage_seconds.get()
    if accumulator is not None:
        accumulator[stage] = accumulator.get(stage, 0.0) + seconds


@contextlib.contextmanager
def capture_inbound_stages():
    """Activate a fresh inbound stage accumulator for the duration of the block."""
    accumulator: dict[str, float] = {}
    token = _inbound_stage_seconds.set(accumulator)
    try:
        yield accumulator
    finally:
        _inbound_stage_seconds.reset(token)


@contextlib.contextmanager
def timed_inbound_stage(stage: str):
    """Time the wrapped work (sync or a single ``await``) into ``stage``.

    Safe to wrap an ``await`` body: the accumulator is read on exit and the
    measurement is wall-clock, which is what the latency breakdown wants.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        record_inbound_stage_seconds(stage, time.perf_counter() - start)


@dataclass
class RequestMetrics:
    """Per-request metrics, finalized into the ``timing_ms`` object (response + log)."""

    session_id: str | None = None
    provider: str | None = None
    model: str | None = None
    entities_detected: dict[str, int] = field(default_factory=dict)
    # Per-stage wall-clock in milliseconds.
    ner_analysis_ms: float = 0.0
    fake_generation_ms: float = 0.0
    redis_write_ms: float = 0.0
    llm_request_ms: float = 0.0
    deanonymization_ms: float = 0.0
    total_ms: float = 0.0
    # True once the chat endpoint has populated the chat-specific fields; the
    # middleware emits chat fields as ``null`` otherwise (non-chat requests).
    is_chat: bool = False

    def timing_ms(self) -> dict[str, float]:
        """The six-stage timing breakdown in milliseconds."""

        # Clamp to >= 0: fake_generation is derived (substitution − redis_write).
        def clamp(value: float) -> float:
            return round(max(value, 0.0), 3)

        return {
            "ner_analysis": clamp(self.ner_analysis_ms),
            "fake_generation": clamp(self.fake_generation_ms),
            "redis_write": clamp(self.redis_write_ms),
            "llm_request": clamp(self.llm_request_ms),
            "deanonymization": clamp(self.deanonymization_ms),
            "total": clamp(self.total_ms),
        }
