"""AES-256-GCM at-rest encryption (Constitution III, research D3).

Only ORIGINAL personal data is encrypted; synthetic fakes and HMAC field names
stay in clear (ratified Constitution v1.1.0). Envelope: ``nonce(12) ‖ ct ‖ tag``.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12  # 96-bit GCM nonce


class Encryptor:
    """Transparent AES-256-GCM encrypt/decrypt over a 32-byte key."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256 requires a 32-byte key")
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + self._aes.encrypt(nonce, plaintext, None)

    def decrypt(self, blob: bytes) -> bytes:
        return self._aes.decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], None)


def key_from_settings(settings) -> bytes:
    """The validated 32-byte key material from ``REDIS_ENCRYPTION_KEY``."""
    return base64.b64decode(settings.redis_encryption_key)
