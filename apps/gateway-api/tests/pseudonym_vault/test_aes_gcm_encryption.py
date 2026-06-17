"""AES-256-GCM properties (T044, FR-008/SC-009, Constitution III)."""

from __future__ import annotations

import pytest

from gateway_api.pseudonym_vault.aes_gcm_encryption import Encryptor


def test_round_trip(enc_key):
    enc = Encryptor(enc_key)
    assert enc.decrypt(enc.encrypt(b"Jan Kowalski")) == b"Jan Kowalski"


def test_distinct_nonces(enc_key):
    enc = Encryptor(enc_key)
    assert enc.encrypt(b"same") != enc.encrypt(b"same")


def test_wrong_key_fails(enc_key):
    blob = Encryptor(enc_key).encrypt(b"secret")
    with pytest.raises(Exception):  # noqa: B017 — InvalidTag
        Encryptor(b"1" * 32).decrypt(blob)


def test_requires_256_bit_key():
    with pytest.raises(ValueError):
        Encryptor(b"too-short")


def test_plaintext_not_present_in_ciphertext(enc_key):
    assert b"secret" not in Encryptor(enc_key).encrypt(b"secret-value")
