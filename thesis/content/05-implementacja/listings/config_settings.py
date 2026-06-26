class Settings(BaseSettings):
    """Pojedynczy obiekt konfiguracji, tworzony raz przy starcie procesu."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    redis_url: str | None = None
    redis_password: str
    redis_encryption_key: str
    redis_session_ttl: int = 1800
    default_model: str = "ollama/qwen2.5:3b"

    @field_validator("redis_encryption_key")
    @classmethod
    def _validate_encryption_key(cls, v: str) -> str:
        """Wymaga base64 dekodującego się do dokładnie 32 bajtów (klucz AES-256)."""
        try:
            decoded = base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "REDIS_ENCRYPTION_KEY must be valid base64 decoding to 32 bytes"
            ) from exc
        if len(decoded) != 32:
            raise ValueError(
                "REDIS_ENCRYPTION_KEY must decode to exactly 32 bytes "
                f"(got {len(decoded)})"
            )
        return v
