_NONCE_BYTES = 12  # 96-bitowy nonce GCM


class Encryptor:
    """Przezroczyste szyfrowanie/odszyfrowanie AES-256-GCM kluczem 32-bajtowym."""

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
    """Szyfruje i odszyfrowuje obiekty JSON-owalne przez Encryptor.

    Każda wartość zapisywana w Redis przechodzi przez tę warstwę.
    """

    def __init__(self, encryptor: Encryptor) -> None:
        self._encryptor = encryptor

    def encrypt_object(self, value) -> bytes:
        return self._encryptor.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def decrypt_object(self, encrypted_value: bytes):
        return json.loads(self._encryptor.decrypt(encrypted_value).decode())
