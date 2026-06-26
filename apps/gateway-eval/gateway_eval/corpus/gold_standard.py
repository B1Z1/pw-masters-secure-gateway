"""The gold-standard schema + JSONL IO + validation (contracts/gold-standard.md).

The single source of ground truth, shared by synthetic and real documents. The
offset/text invariant (``text[start:end] == entity.text``) is enforced as a hard
error on load and on build — a wrong offset is never silently skipped (D1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

from .entity_vocabulary import CANONICAL_TYPES

Source = Literal["synthetic", "real"]


class GoldEntity(BaseModel):
    """One known PII instance, with character offsets into the document text."""

    type: str
    start: int
    end: int
    text: str

    @model_validator(mode="after")
    def _check_type_and_span(self) -> GoldEntity:
        if self.type not in CANONICAL_TYPES:
            raise ValueError(
                f"unknown gold type {self.type!r} "
                f"(allowed: {', '.join(CANONICAL_TYPES)})"
            )
        if not (0 <= self.start < self.end):
            raise ValueError(f"bad span [{self.start}, {self.end}) for {self.type}")
        return self


class GoldDocument(BaseModel):
    """One corpus document plus all its known PII instances."""

    doc_id: str
    source: Source
    contract_type: str
    text: str
    entities: list[GoldEntity]

    @model_validator(mode="after")
    def _check_offsets_and_overlap(self) -> GoldDocument:
        document_length = len(self.text)
        for entity in self.entities:
            if entity.end > document_length:
                raise ValueError(
                    f"{self.doc_id}: entity end {entity.end} exceeds text length "
                    f"{document_length}"
                )
            spanned = self.text[entity.start : entity.end]
            if spanned != entity.text:
                raise ValueError(
                    f"{self.doc_id}: offset/text mismatch for {entity.type} at "
                    f"[{entity.start}, {entity.end}): text has {spanned!r}, gold has "
                    f"{entity.text!r}"
                )
        self._reject_same_type_overlap()
        return self

    def _reject_same_type_overlap(self) -> None:
        by_type: dict[str, list[GoldEntity]] = {}
        for entity in self.entities:
            by_type.setdefault(entity.type, []).append(entity)
        for entity_type, group in by_type.items():
            ordered = sorted(group, key=lambda item: item.start)
            for previous, following in zip(ordered, ordered[1:], strict=False):
                if following.start < previous.end:
                    raise ValueError(
                        f"{self.doc_id}: overlapping {entity_type} spans "
                        f"[{previous.start},{previous.end}) and "
                        f"[{following.start},{following.end})"
                    )


def load_jsonl(path: Path) -> list[GoldDocument]:
    """Load and validate every line of a gold JSONL file."""
    documents: list[GoldDocument] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            documents.append(GoldDocument.model_validate_json(stripped))
        except Exception as validation_error:
            raise ValueError(f"{path}:{line_number}: {validation_error}") from None
    return documents


def load_corpus(*directories: Path) -> list[GoldDocument]:
    """Load every ``*.jsonl`` file under the given directories (sorted, deduped)."""
    documents: list[GoldDocument] = []
    seen_ids: set[str] = set()
    for directory in directories:
        if not directory.exists():
            continue
        for jsonl_path in sorted(directory.glob("*.jsonl")):
            for document in load_jsonl(jsonl_path):
                if document.doc_id in seen_ids:
                    raise ValueError(f"duplicate doc_id {document.doc_id!r}")
                seen_ids.add(document.doc_id)
                documents.append(document)
    return documents


def write_jsonl(path: Path, documents: list[GoldDocument]) -> None:
    """Write documents as one JSON object per line (UTF-8, no ASCII escapes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(document.model_dump(), ensure_ascii=False) for document in documents
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def corpus_stats(documents: list[GoldDocument]) -> dict:
    """Counts used for the targets check + the aggregate report (FR-007/SC-001)."""
    by_type: dict[str, int] = {}
    by_source: dict[str, int] = {"synthetic": 0, "real": 0}
    total_entities = 0
    for document in documents:
        by_source[document.source] = by_source.get(document.source, 0) + 1
        for entity in document.entities:
            by_type[entity.type] = by_type.get(entity.type, 0) + 1
            total_entities += 1
    document_count = len(documents) or 1
    synthetic_ratio = by_source["synthetic"] / document_count
    return {
        "n_docs": len(documents),
        "n_entities": total_entities,
        "by_type": by_type,
        "by_source": by_source,
        "types_present": sorted(by_type),
        "all_types_present": all(t in by_type for t in CANONICAL_TYPES),
        "synthetic_ratio": round(synthetic_ratio, 3),
    }
