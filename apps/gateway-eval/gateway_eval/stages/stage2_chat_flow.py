"""Stage 2 — full chat flow with the Echo provider (FR-023..FR-026).

Per document: POST /v1/chat/completions with ``model="echo/echo"``. Echo returns the
(pseudonymized) last user turn, which the gateway de-pseudonymizes — a clean,
deterministic, offline round-trip. Gathers the gateway's declared outbound text (for
the leak audit), the restored answer (for the round-trip check), and the per-stage
``timing_ms``. A fresh session per document is deleted afterwards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from ..config import EvaluationConfig
from ..corpus.gold_standard import GoldDocument
from ..gateway_client.evaluation_client import GatewayClientError


@dataclass
class Stage2Outcome:
    doc_id: str
    pseudonymized_content: str = ""
    fake_values: list[str] = field(default_factory=list)
    answer: str = ""
    timing_ms: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def run_stage2(
    client, document: GoldDocument, config: EvaluationConfig
) -> Stage2Outcome:
    session_id = uuid.uuid4().hex
    outcome = Stage2Outcome(doc_id=document.doc_id)
    try:
        chat = await client.chat_completions(
            document.text, session_id, config.echo_model
        )
        outcome.pseudonymized_content = chat.pseudonymized_content
        outcome.fake_values = chat.fake_values
        outcome.answer = chat.answer
        outcome.timing_ms = chat.timing_ms
    except GatewayClientError as gateway_error:
        outcome.errors.append(f"stage2: {gateway_error}")
    finally:
        await client.delete_session(session_id)
    return outcome
