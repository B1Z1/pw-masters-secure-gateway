"""Mapping-key strategy + HMAC field names (T033, FR-024/FR-025/FR-026)."""

from __future__ import annotations

from gateway_api.pseudonym_vault.mapping_keys import fwd_field, mapping_key


def test_separator_insensitive_identifier():
    assert mapping_key("PESEL", "90010112345") == mapping_key("PESEL", "900-101-123-45")


def test_name_uses_lemma_lowercased():
    assert mapping_key("PERSON", "Kowalskiego", lemma="Kowalski") == "kowalski"


def test_same_literal_two_types_distinct(enc_key):
    k = "1234567890"
    assert fwd_field(enc_key, "PESEL", k) != fwd_field(enc_key, "NIP", k)


def test_separator_variants_same_field(enc_key):
    a = fwd_field(enc_key, "PESEL", mapping_key("PESEL", "90010112345"))
    b = fwd_field(enc_key, "PESEL", mapping_key("PESEL", "900-101-123-45"))
    assert a == b


def test_hmac_field_carries_no_pii(enc_key):
    field = fwd_field(enc_key, "PESEL", "90010112345")
    assert field.startswith("fwd:")
    assert "90010112345" not in field
