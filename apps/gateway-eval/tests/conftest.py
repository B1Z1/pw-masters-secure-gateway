"""Shared fixtures for the gateway-eval test suite.

Valid gateway-api env vars are set at import time (before any ``gateway_api`` import)
so its fail-fast settings validation does not abort collection. The end-to-end tests
drive the harness against a deterministic in-process ``FakeGateway`` (no network, no
Redis, no spaCy) that mimics the gateway contract — keeping CI hermetic and
reproducible. Live validation against the real stack is covered by quickstart.md.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

os.environ.setdefault("REDIS_PASSWORD", "testpass")
os.environ.setdefault("REDIS_ENCRYPTION_KEY", base64.b64encode(b"0" * 32).decode())
os.environ.setdefault("REDIS_URL", "redis://:testpass@localhost:6379/0")

import pytest  # noqa: E402

from gateway_eval.corpus.entity_vocabulary import is_structured  # noqa: E402
from gateway_eval.corpus.gold_standard import GoldDocument, load_jsonl  # noqa: E402
from gateway_eval.gateway_client.evaluation_client import (  # noqa: E402
    ChatView,
    DepseudonymizeView,
    DetectedSpan,
    HealthView,
    PseudonymizeView,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Reverse of entity_vocabulary aliases: a canonical type → a representative gateway
# label, so the FakeGateway exercises the harness's label-normalization path (D8).
_CANONICAL_TO_GATEWAY_LABEL = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "ADDRESS": "POLISH_ADDRESS",
    "PESEL": "PESEL",
    "NIP": "NIP",
    "REGON": "REGON",
    "BANK_ACCOUNT": "POLISH_BANK_ACCOUNT",
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "DATE_TIME": "DATE_TIME",
}


@pytest.fixture
def sample_corpus_path() -> Path:
    return FIXTURES / "sample_gold.jsonl"


@pytest.fixture
def sample_corpus(sample_corpus_path: Path) -> list[GoldDocument]:
    return load_jsonl(sample_corpus_path)


class FakeGateway:
    """A deterministic, in-process stand-in for the live gateway.

    Built from the gold corpus so it behaves like a *good* gateway: it detects gold
    spans (minus any ``miss_types``), replaces them with stable fakes, and restores
    them on the way back. The harness still scores its outputs against gold
    independently — the fake is never consulted as ground truth. ``leak_types`` lets a
    test force an original (in inflected form) to survive into the outbound text.
    """

    def __init__(
        self,
        documents: list[GoldDocument],
        *,
        miss_types: frozenset[str] = frozenset(),
        leak_types: frozenset[str] = frozenset(),
        spurious: bool = False,
    ) -> None:
        self._by_text = {document.text: document for document in documents}
        self._miss_types = miss_types
        self._leak_types = leak_types
        self._spurious = spurious
        self._sessions: dict[str, dict[str, str]] = {}

    async def __aenter__(self) -> FakeGateway:
        return self

    async def __aexit__(self, *exception_info: object) -> None:
        return None

    async def health(self) -> HealthView:
        return HealthView(status="ok", dependencies={"redis": "ok", "spacy_model": "ok"})

    def _detected_entities(self, document: GoldDocument):
        return [e for e in document.entities if e.type not in self._miss_types]

    async def detect(self, text: str) -> list[DetectedSpan]:
        document = self._by_text.get(text)
        if document is None:
            return []
        spans = [
            DetectedSpan(
                entity_type=_CANONICAL_TO_GATEWAY_LABEL[entity.type],
                start=entity.start,
                end=entity.end,
                score=0.99,
                text=entity.text,
            )
            for entity in self._detected_entities(document)
        ]
        if self._spurious:
            spans.append(
                DetectedSpan(entity_type="ORGANIZATION", start=0, end=5, score=0.5)
            )
        return spans

    def _fake_for(self, entity_type: str, index: int) -> str:
        if is_structured(entity_type):
            return f"00000000{index:03d}"
        return f"Synteo{entity_type.title().replace('_', '')}{index}"

    async def pseudonymize(self, text: str, session_id: str) -> PseudonymizeView:
        document = self._by_text.get(text)
        mapping = self._sessions.setdefault(session_id, {})
        if document is None:
            return PseudonymizeView(pseudonymized_text=text, session_id=session_id)
        # Replace right-to-left so earlier offsets stay valid.
        out = text
        for index, entity in enumerate(
            sorted(self._detected_entities(document), key=lambda e: e.start, reverse=True)
        ):
            if entity.type in self._leak_types:
                fake = entity.text + "ego"  # inflected original survives → a leak
            else:
                fake = self._fake_for(entity.type, index)
                mapping[fake] = entity.text
            out = out[: entity.start] + fake + out[entity.end :]
        return PseudonymizeView(pseudonymized_text=out, session_id=session_id)

    async def depseudonymize(self, text: str, session_id: str) -> DepseudonymizeView:
        restored = text
        for fake, original in self._sessions.get(session_id, {}).items():
            restored = restored.replace(fake, original)
        return DepseudonymizeView(restored_text=restored, session_id=session_id)

    async def chat_completions(
        self, text: str, session_id: str, model: str
    ) -> ChatView:
        pseudo = await self.pseudonymize(text, session_id)
        # Echo provider returns the (pseudonymized) last user turn; gateway restores it.
        restored = await self.depseudonymize(pseudo.pseudonymized_text, session_id)
        return ChatView(
            answer=restored.restored_text,
            session_id=session_id,
            pseudonymized_content=pseudo.pseudonymized_text,
            timing_ms={
                "ner_analysis": 1.0,
                "fake_generation": 1.0,
                "redis_write": 1.0,
                "llm_request": 0.0,
                "deanonymization": 1.0,
                "total": 4.0,
            },
            provider="echo",
        )

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


@pytest.fixture
def fake_gateway_factory(sample_corpus):
    def _make(**kwargs) -> FakeGateway:
        return FakeGateway(sample_corpus, **kwargs)

    return _make
