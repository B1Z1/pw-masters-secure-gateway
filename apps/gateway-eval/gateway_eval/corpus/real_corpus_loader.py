"""Ingest path for manually-annotated real contracts (FR-013/FR-014, research D6).

Real documents are annotated by the researcher to the shared gold schema and kept
under the git-ignored ``corpus/data/real/`` directory — never committed, never
published. This loader is the gatekeeper: it enforces the same validation as the
synthetic corpus (offset==text invariant) and rejects anything not marked
``source="real"``.
"""

from __future__ import annotations

from pathlib import Path

from .gold_standard import GoldDocument, load_jsonl


def load_real_corpus(real_dir: Path) -> list[GoldDocument]:
    """Load + validate every real gold JSONL file; require ``source == "real"``."""
    if not real_dir.exists():
        return []
    documents: list[GoldDocument] = []
    for jsonl_path in sorted(real_dir.glob("*.jsonl")):
        for document in load_jsonl(jsonl_path):
            if document.source != "real":
                raise ValueError(
                    f"{jsonl_path}: document {document.doc_id!r} under data/real/ must "
                    f'have source="real" (got {document.source!r})'
                )
            documents.append(document)
    return documents
