"""AES-256-GCM at-rest encryption (Constitution III, research D3).

Only ORIGINAL personal data is encrypted; synthetic fakes and HMAC field names
stay in clear (ratified Constitution v1.1.0). Envelope: ``nonce(12) ‖ ct ‖ tag``.
"""

from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12  # 96-bit GCM nonce


class Encryptor:
    """Transparent AES-256-GCM encrypt/decrypt over a 32-byte key."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256 requires a 32-byte key")
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + self._cipher.encrypt(nonce, plaintext, None)

    def decrypt(self, encrypted_envelope: bytes) -> bytes:
        return self._cipher.decrypt(
            encrypted_envelope[:_NONCE_BYTES], encrypted_envelope[_NONCE_BYTES:], None
        )


class EncryptedJsonCodec:
    """Seal/open JSON-serializable objects through an :class:`Encryptor`.

    The reversible boundary between in-memory mappings and their AES-256-GCM
    ciphertext at rest — every Redis value passes through here.
    """

    def __init__(self, encryptor: Encryptor) -> None:
        self._encryptor = encryptor

    def encrypt_object(self, value) -> bytes:
        return self._encryptor.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def decrypt_object(self, encrypted_value: bytes):
        return json.loads(self._encryptor.decrypt(encrypted_value).decode())


def key_from_settings(settings) -> bytes:
    """The validated 32-byte key material from ``REDIS_ENCRYPTION_KEY``."""
    return base64.b64decode(settings.redis_encryption_key)
