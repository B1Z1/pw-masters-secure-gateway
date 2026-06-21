"""Epic 6 provider discovery — GET /v1/providers (FR-011/FR-012).

Read-only: lets the config panel populate the provider choice and warn "no API
key configured" BEFORE the first message. Returns only ``{name, requires_key,
key_configured}`` — never a key value (keys are server-side ``.env`` only and are
never accepted from the client). Stateless (no Redis) → gate-exempt, so the panel
renders even when Redis is down.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()


class ProviderDescriptor(BaseModel):
    name: str
    requires_key: bool
    key_configured: bool


@router.get("/v1/providers", response_model=list[ProviderDescriptor])
async def list_providers() -> list[ProviderDescriptor]:
    settings = get_settings()

    # Presence only — the boolean reflects whether the server holds the key; the
    # value itself never crosses the boundary (FR-012).
    return [
        ProviderDescriptor(
            name="openai",
            requires_key=True,
            key_configured=bool(settings.openai_api_key),
        ),
        ProviderDescriptor(
            name="anthropic",
            requires_key=True,
            key_configured=bool(settings.anthropic_api_key),
        ),
        ProviderDescriptor(name="ollama", requires_key=False, key_configured=False),
    ]
