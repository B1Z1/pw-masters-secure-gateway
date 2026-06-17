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

from pydantic import BaseModel

from ..llm_providers.base import ChatMessage
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


class AnonymizationPipeline:
    def __init__(self, engine, store) -> None:
        self._engine = engine
        self._store = store

    async def pseudonymize_text(
            self, session_id: str, text: str
    ) -> tuple[str, list[Replacement]]:
        """Detect + substitute PII in one string; return (fake_text, replacements)."""
        if not text or not text.strip():
            return text, []

        entities = self._engine.detect(text)
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

    async def pseudonymize_messages(
            self, session_id: str, messages: list[ChatMessage]
    ) -> list[ChatMessage]:
        """Pseudonymize EVERY message each turn (FR-005); roles preserved.

        Re-pseudonymizing content already seen in the session is deterministic
        (same original → same fake) thanks to Epic 3 session consistency (FR-006),
        so no original re-entering through an earlier assistant message can reach
        the LLM (the gateway↔LLM hop is the protected one — FR-007).
        """
        pseudonymized: list[ChatMessage] = []

        for message in messages:
            fake_content, _ = await self.pseudonymize_text(session_id, message.content)
            pseudonymized.append(
                ChatMessage(role=message.role, content=fake_content)
            )

        return pseudonymized

    async def depseudonymize_text(self, session_id: str, text: str) -> str:
        """Restore originals in the LLM answer: exact + inflection, then fuzzy."""
        return await self._store.restore_text(session_id, text, fuzzy=True)


def get_pipeline() -> AnonymizationPipeline | None:
    """Build the pipeline from the process-wide engine + store, or None."""
    store = get_mapping_store()

    if store is None:
        return None

    return AnonymizationPipeline(get_engine(), store)
