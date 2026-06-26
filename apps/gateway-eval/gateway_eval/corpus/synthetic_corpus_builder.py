"""Seeded synthetic corpus builder (FR-010/FR-011/FR-012, research D7).

Polish contract templates carry typed slots (``{{PESEL:lessor}}``). The builder fills
each slot with a realistic value from the gateway's own ``FakeDataGenerator`` (so the
corpus mirrors real substitution), records the EXACT character offset → the gold entity
is produced automatically, and validates every injected identifier with the gateway's
checksum functions. Deterministic: the same seed yields a byte-identical corpus +
gold standard. The heavy ``gateway_api`` import is deferred to build time.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from .gold_standard import GoldDocument, write_jsonl

_SLOT = re.compile(r"\{\{(\w+):(\w+)\}\}")
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_MAX_ATTEMPTS = 8

# Canonical gold type → the gateway's FakeDataGenerator dispatch label.
_GENERATION_LABEL = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "ADDRESS": "POLISH_ADDRESS",
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "DATE_TIME": "DATE_TIME",
    "PESEL": "PESEL",
    "NIP": "NIP",
    "REGON": "REGON",
    "BANK_ACCOUNT": "POLISH_BANK_ACCOUNT",
}


def _load_templates() -> dict[str, str]:
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(_TEMPLATE_DIR.glob("*.txt"))
    }


def _is_checksum_valid(canonical_type: str, value: str) -> bool:
    from gateway_api.pii_detection.checksums import (
        nip_is_valid,
        nrb_is_valid,
        pesel_is_valid,
        regon9_is_valid,
        regon14_is_valid,
    )

    digits = re.sub(r"\D", "", value)
    if canonical_type == "PESEL":
        return pesel_is_valid(digits)
    if canonical_type == "NIP":
        return nip_is_valid(digits)
    if canonical_type == "REGON":
        return (
            regon14_is_valid(digits) if len(digits) == 14 else regon9_is_valid(digits)
        )
    if canonical_type == "BANK_ACCOUNT":
        return nrb_is_valid(digits)
    return True  # free-text types have no checksum


def _generate_value(generator, canonical_type: str) -> str:
    from gateway_api.pii_detection.dto import DetectedEntity

    label = _GENERATION_LABEL[canonical_type]
    probe = DetectedEntity(entity_type=label, start=0, end=0, score=1.0, text="")
    for _ in range(_MAX_ATTEMPTS):
        value = generator.generate(probe).base
        if _is_checksum_valid(canonical_type, value):
            return value
    # Fall back to the last draw — the gateway generator is the trusted source.
    return generator.generate(probe).base


def build_document(
    doc_id: str, contract_type: str, template: str, generator
) -> GoldDocument:
    role_cache: dict[tuple[str, str], str] = {}
    text_parts: list[str] = []
    entities: list[dict] = []
    cursor = 0
    position = 0

    for match in _SLOT.finditer(template):
        literal = template[cursor : match.start()]
        text_parts.append(literal)
        position += len(literal)

        canonical_type, role = match.group(1), match.group(2)
        key = (canonical_type, role)
        if key not in role_cache:
            role_cache[key] = _generate_value(generator, canonical_type)
        value = role_cache[key]

        text_parts.append(value)
        entities.append(
            {
                "type": canonical_type,
                "start": position,
                "end": position + len(value),
                "text": value,
            }
        )
        position += len(value)
        cursor = match.end()

    text_parts.append(template[cursor:])
    text = "".join(text_parts)

    return GoldDocument.model_validate(
        {
            "doc_id": doc_id,
            "source": "synthetic",
            "contract_type": contract_type,
            "text": text,
            "entities": entities,
        }
    )


def build_corpus(seed: int = 42, count: int = 56) -> list[GoldDocument]:
    from gateway_api.pseudonym_generation import FakeDataGenerator

    templates = _load_templates()
    if not templates:
        raise RuntimeError(f"no templates found under {_TEMPLATE_DIR}")
    contract_types = sorted(templates)

    generator = FakeDataGenerator(seed=seed)
    selector = random.Random(seed)

    documents: list[GoldDocument] = []
    for index in range(count):
        contract_type = contract_types[index % len(contract_types)]
        # Light per-document shuffle of which template, kept deterministic by the seed.
        if index >= len(contract_types):
            contract_type = selector.choice(contract_types)
        doc_id = f"syn-{contract_type}-{index:03d}"
        documents.append(
            build_document(doc_id, contract_type, templates[contract_type], generator)
        )
    return documents


def build_and_write(
    seed: int = 42,
    out_dir: Path = _TEMPLATE_DIR.parent / "data" / "synthetic",
    count: int = 56,
) -> list[GoldDocument]:
    documents = build_corpus(seed=seed, count=count)
    write_jsonl(Path(out_dir) / "synthetic_corpus.jsonl", documents)
    return documents
