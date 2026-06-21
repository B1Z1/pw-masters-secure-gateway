"""GET /v1/providers — key-presence discovery, key-safety, gate-exempt (Epic 6, US3)."""

from __future__ import annotations

from types import SimpleNamespace


def _patch_settings(monkeypatch, *, openai, anthropic):
    monkeypatch.setattr(
        "gateway_api.api.providers.get_settings",
        lambda: SimpleNamespace(openai_api_key=openai, anthropic_api_key=anthropic),
    )


async def test_lists_three_providers_with_key_presence(client, monkeypatch):
    _patch_settings(monkeypatch, openai="sk-secret-value", anthropic=None)

    resp = await client.get("/v1/providers")
    assert resp.status_code == 200
    by_name = {entry["name"]: entry for entry in resp.json()}

    assert by_name["openai"] == {
        "name": "openai",
        "requires_key": True,
        "key_configured": True,
    }
    assert by_name["anthropic"] == {
        "name": "anthropic",
        "requires_key": True,
        "key_configured": False,
    }
    assert by_name["ollama"] == {
        "name": "ollama",
        "requires_key": False,
        "key_configured": False,
    }
    # No key value ever crosses the boundary (FR-012).
    assert "sk-secret-value" not in resp.text


async def test_providers_answers_while_redis_down(client, monkeypatch):
    """Gate-exempt: the config panel must populate even in a degraded stack."""

    async def _redis_down():
        return "unavailable"

    monkeypatch.setattr("gateway_api.main.check_redis", _redis_down)
    _patch_settings(monkeypatch, openai=None, anthropic=None)

    resp = await client.get("/v1/providers")
    assert resp.status_code == 200
    assert len(resp.json()) == 3
