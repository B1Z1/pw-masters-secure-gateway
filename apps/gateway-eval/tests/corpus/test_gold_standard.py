"""T013 — gold-standard schema, IO, and validation (contracts/gold-standard.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gateway_eval.corpus.gold_standard import (
    GoldDocument,
    corpus_stats,
    load_jsonl,
    write_jsonl,
)


def _doc(**overrides) -> dict:
    base = {
        "doc_id": "d1",
        "source": "synthetic",
        "contract_type": "najem",
        "text": "Najemca Jan Kowalski.",
        "entities": [{"type": "PERSON", "start": 8, "end": 20, "text": "Jan Kowalski"}],
    }
    base.update(overrides)
    return base


def test_valid_document_passes():
    document = GoldDocument.model_validate(_doc())
    assert document.entities[0].text == "Jan Kowalski"


def test_offset_text_mismatch_is_hard_error():
    bad = _doc(entities=[{"type": "PERSON", "start": 0, "end": 7, "text": "Jan Kowalski"}])
    with pytest.raises(ValidationError):
        GoldDocument.model_validate(bad)


def test_end_beyond_text_is_rejected():
    bad = _doc(entities=[{"type": "PERSON", "start": 8, "end": 999, "text": "Jan Kowalski"}])
    with pytest.raises(ValidationError):
        GoldDocument.model_validate(bad)


def test_unknown_type_is_rejected():
    bad = _doc(entities=[{"type": "CREDIT_CARD", "start": 8, "end": 20, "text": "Jan Kowalski"}])
    with pytest.raises(ValidationError):
        GoldDocument.model_validate(bad)


def test_same_type_overlap_is_rejected():
    text = "AAAA BBBB"
    bad = _doc(
        text=text,
        entities=[
            {"type": "PERSON", "start": 0, "end": 5, "text": "AAAA "},
            {"type": "PERSON", "start": 4, "end": 9, "text": " BBBB"},
        ],
    )
    with pytest.raises(ValidationError):
        GoldDocument.model_validate(bad)


def test_jsonl_round_trip(tmp_path):
    documents = [GoldDocument.model_validate(_doc())]
    path = tmp_path / "gold.jsonl"
    write_jsonl(path, documents)
    reloaded = load_jsonl(path)
    assert reloaded == documents


def test_load_reports_line_number_on_bad_offset(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '{"doc_id":"d1","source":"synthetic","contract_type":"najem",'
        '"text":"abc","entities":[{"type":"PERSON","start":0,"end":2,"text":"zz"}]}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bad.jsonl:1"):
        load_jsonl(path)


def test_corpus_stats_counts_types_and_sources(sample_corpus):
    stats = corpus_stats(sample_corpus)
    assert stats["n_docs"] == 6
    assert stats["n_entities"] == 26
    assert stats["all_types_present"] is True
    assert stats["by_source"]["synthetic"] == 6
