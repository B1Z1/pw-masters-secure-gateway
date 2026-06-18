"""Application configuration (F-02).

All runtime configuration is loaded once from environment variables via
``pydantic-settings``. The security-critical ``REDIS_ENCRYPTION_KEY`` is
validated here so that an invalid key aborts startup before any request is
served (fail-fast — FR-019, SC-003, Constitution III).
"""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single configuration object, instantiated once at process start."""

    model_config = SettingsConfigDict(
        # "../../.env" lets the natively-run backend (cwd apps/gateway-api) find
        # the repo-root .env; in containers config arrives as real env vars.
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Redis (session & encrypted mapping store) ---
    # Optional to *start* the process; absence degrades to health-only
    # (503 on every non-health route — FR-027).
    redis_url: str | None = None
    redis_password: str
    redis_encryption_key: str
    # Epic 3 (FR-009, clarification 2026-06-16): default session TTL = 30 minutes
    # (sliding — refreshed on every mapping-store operation).
    redis_session_ttl: int = 1800

    # --- Detection thresholds (Epic 2) ---
    # Optional path to the per-type threshold YAML. The threshold *values* are
    # read live from this file by detection/thresholds.py (NOT via this cached
    # Settings object) so changes apply without a restart (FR-020). Absent → the
    # shipped default_thresholds.yaml is used.
    detection_thresholds_path: str | None = None

    # --- LLM providers (optional at startup; error only on first use — FR-020) ---
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://host.docker.internal:11434"
    # Epic 4 (FR-022): per-request Ollama timeout; an exceeded call → 504.
    ollama_timeout: float = 60.0
    # Epic 5 (FR-010): Anthropic requires an explicit max-output-tokens on every
    # call; it comes from configuration.
    anthropic_max_tokens: int = 4096
    # Epic 5 (FR-016/FR-017): provider selection is by model prefix via the router,
    # so the single source of truth is default_model (the Epic 4 DEFAULT_LLM_PROVIDER
    # setting is removed). The default is a local Ollama model so the keyless, offline
    # demo works out of the box; its "ollama/" prefix routes to the Ollama adapter.
    default_model: str = "ollama/qwen2.5:3b"

    @field_validator("redis_encryption_key")
    @classmethod
    def _validate_encryption_key(cls, v: str) -> str:
        """Require base64 that decodes to exactly 32 bytes (AES-256 key material)."""
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


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached settings. Raises on invalid configuration."""
    return Settings()
