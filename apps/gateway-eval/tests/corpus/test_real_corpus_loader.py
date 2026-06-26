"""T033 — real corpus loader: validates annotation, rejects bad source/offsets."""

from __future__ import annotations

import pytest

from gateway_eval.corpus.real_corpus_loader import load_real_corpus


def test_missing_dir_returns_empty(tmp_path):
    assert load_real_corpus(tmp_path / "nope") == []


def test_loads_real_marked_documents(tmp_path):
    (tmp_path / "r1.jsonl").write_text(
        '{"doc_id":"real-001","source":"real","contract_type":"najem",'
        '"text":"Najemca Jan Kowalski.","entities":'
        '[{"type":"PERSON","start":8,"end":20,"text":"Jan Kowalski"}]}\n',
        encoding="utf-8",
    )
    documents = load_real_corpus(tmp_path)
    assert len(documents) == 1
    assert documents[0].source == "real"


def test_rejects_non_real_source(tmp_path):
    (tmp_path / "bad.jsonl").write_text(
        '{"doc_id":"x","source":"synthetic","contract_type":"najem",'
        '"text":"abc","entities":[]}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match='must.*source="real"'):
        load_real_corpus(tmp_path)


def test_rejects_bad_offset(tmp_path):
    (tmp_path / "bad.jsonl").write_text(
        '{"doc_id":"x","source":"real","contract_type":"najem",'
        '"text":"abc","entities":[{"type":"PERSON","start":0,"end":2,"text":"zz"}]}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_real_corpus(tmp_path)
