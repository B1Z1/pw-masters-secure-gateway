"""AnonymizationPipeline — the Epic 4 orchestrator (FR-001..FR-007).

Inbound: detect PII (Epic 2) → substitute session-consistent fakes (Epic 3 store)
→ persist. Outbound: restore originals in the LLM answer (exact + inflection,
then the fuzzy fallback). Reuses ``DetectionEngine`` and ``MappingStore`` — it
does NOT reimplement them. The inbound substitution that used to live inline in
``api/pseudonymize.py`` lives here now (FR-003); both that debug endpoint and the
chat endpoint consume this single implementation.

Logs carry session_id + entity types/counts only — never content, originals, or
fakes (Constitution VIII, FR-024).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel

from ..llm_providers.base import ChatMessage
from ..observability.request_metrics import (
    capture_inbound_stages,
    timed_inbound_stage,
)
from ..pii_detection.engine import get_engine
from ..pseudonym_vault.mapping_store import get_mapping_store

logger = logging.getLogger("gateway_api")


class Replacement(BaseModel):
    """One substitution performed inbound (offsets into the ORIGINAL text)."""

    entity_type: str
    original: str
    fake: str
    start: int  # offset into the ORIGINAL text
    end: int


@dataclass
class InboundTiming:
    """Per-stage inbound wall-clock in milliseconds (Epic 6, FR-014/D4)."""

    ner_analysis_ms: float = 0.0
    fake_generation_ms: float = 0.0
    redis_write_ms: float = 0.0


@dataclass
class InboundResult:
    """Everything one inbound pass produces for the chat response (Epic 6)."""

    fake_messages: list[ChatMessage]
    entities_detected: dict[str, int] = field(default_factory=dict)
    total_entities: int = 0
    last_user_pseudonymized: str = ""
    last_user_replacements: list[Replacement] = field(default_factory=list)
    timing: InboundTiming = field(default_factory=InboundTiming)


class AnonymizationPipeline:
    def __init__(self, engine, store) -> None:
        self._engine = engine
        self._store = store

    async def run_inbound(
            self, session_id: str, messages: list[ChatMessage]
    ) -> InboundResult:
        """Pseudonymize the WHOLE history once, returning the data the chat
        response and the log line need (Epic 6, FR-005/FR-006/FR-015).

        Every message is pseudonymized each turn (deterministic per Epic 3
        session consistency, FR-006), so no original re-entering through an
        earlier assistant message can reach the LLM. Per-type counts are summed
        over the whole history; the latest user message's synthetic text +
        replacements are captured for ``input_anonymization``. Inbound stage
        timings are attributed via the request-scoped accumulator (D4).
        """
        last_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].role == "user"
            ),
            None,
        )

        fake_messages: list[ChatMessage] = []
        entities_detected: dict[str, int] = {}
        last_user_pseudonymized = ""
        last_user_replacements: list[Replacement] = []

        with capture_inbound_stages() as stage_seconds:
            for index, message in enumerate(messages):
                fake_content, replacements = await self.pseudonymize_text(
                    session_id, message.content
                )
                fake_messages.append(
                    ChatMessage(role=message.role, content=fake_content)
                )

                for replacement in replacements:
                    entities_detected[replacement.entity_type] = (
                        entities_detected.get(replacement.entity_type, 0) + 1
                    )

                if index == last_user_index:
                    last_user_pseudonymized = fake_content
                    last_user_replacements = replacements

        redis_write_ms = stage_seconds.get("redis_write", 0.0) * 1000
        # fake_generation = substitution compute − the inbound Redis-write time
        # captured within it (D4); a small amount of inbound read time folds in.
        fake_generation_ms = (
            stage_seconds.get("substitution", 0.0) * 1000 - redis_write_ms
        )

        return InboundResult(
            fake_messages=fake_messages,
            entities_detected=entities_detected,
            total_entities=sum(entities_detected.values()),
            last_user_pseudonymized=last_user_pseudonymized,
            last_user_replacements=last_user_replacements,
            timing=InboundTiming(
                ner_analysis_ms=stage_seconds.get("ner_analysis", 0.0) * 1000,
                fake_generation_ms=max(fake_generation_ms, 0.0),
                redis_write_ms=redis_write_ms,
            ),
        )

    async def depseudonymize_text(self, session_id: str, text: str) -> str:
        """Restore originals in the LLM answer: exact + inflection, then fuzzy."""
        return await self._store.restore_text(session_id, text, fuzzy=True)

    async def increment_message_count(self, session_id: str) -> None:
        """+1 successful chat round-trip (delegates to the store; no-op if no state)."""
        await self._store.increment_message_count(session_id)

    async def pseudonymize_text(
            self, session_id: str, text: str
    ) -> tuple[str, list[Replacement]]:
        """Detect + substitute PII in one string; return (fake_text, replacements)."""
        if not text or not text.strip():
            return text, []

        with timed_inbound_stage("ner_analysis"):
            entities = self._engine.detect(text)

        # The store's inbound Redis writes time themselves into "redis_write"
        # within this window; the remainder is fake-generation compute (D4).
        with timed_inbound_stage("substitution"):
            items = [
                (entity, await self._store.get_or_create(session_id, entity))
                for entity in entities
            ]

        fake_text = text

        for entity, fake_form in sorted(
                items, key=lambda pair: pair[0].start, reverse=True
        ):
            fake_text = fake_text[: entity.start] + fake_form + fake_text[entity.end:]

        replacements = [
            Replacement(
                entity_type=entity.entity_type,
                original=entity.text,
                fake=fake_form,
                start=entity.start,
                end=entity.end,
            )
            for entity, fake_form in items
        ]

        logger.info(
            "pseudonymize session=%s entities=%d types=%s",
            session_id,
            len(items),
            sorted({entity.entity_type for entity, _ in items}),
        )

        return fake_text, replacements


def get_pipeline() -> AnonymizationPipeline | None:
    """Build the pipeline from the process-wide engine + store, or None."""
    store = get_mapping_store()

    if store is None:
        return None

    return AnonymizationPipeline(get_engine(), store)
