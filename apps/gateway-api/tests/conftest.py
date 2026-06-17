"""Shared pytest fixtures for the gateway-api test suite.

A valid configuration environment is established at import time (before the app
module is imported) so that fail-fast settings validation does not abort
collection. Individual tests patch ``gateway_api.health.get_redis_client`` to
drive Redis behavior.
"""

from __future__ import annotations

import base64
import os

# Valid 32-byte (base64) AES key + required Redis settings, set before the app
# module is imported anywhere.
os.environ.setdefault("REDIS_PASSWORD", "testpass")
os.environ.setdefault("REDIS_ENCRYPTION_KEY", base64.b64encode(b"0" * 32).decode())
os.environ.setdefault("REDIS_URL", "redis://:testpass@localhost:6379/0")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """An httpx.AsyncClient bound to the ASGI app (no network)."""
    from gateway_api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Detection (Epic 2) fixtures -------------------------------------------


@pytest.fixture
def model_ready(monkeypatch):
    """Report the spaCy model as loaded without actually loading it."""
    monkeypatch.setattr("gateway_api.pii_detection.nlp.is_model_ready", lambda: True)


@pytest.fixture
def model_not_ready(monkeypatch):
    """Report the spaCy model as not loaded."""
    monkeypatch.setattr("gateway_api.pii_detection.nlp.is_model_ready", lambda: False)


@pytest.fixture
def patch_analyzer(monkeypatch):
    """Replace the engine's AnalyzerEngine with a fake returning canned results.

    Lets the full detect() pipeline (DTO mapping, overlap, thresholds) be tested
    without loading pl_core_news_lg.
    """

    def _patch(results):
        class _FakeAnalyzer:
            def analyze(self, text, language, entities):
                return list(results)

        monkeypatch.setattr(
            "gateway_api.pii_detection.engine._get_analyzer", lambda: _FakeAnalyzer()
        )

    return _patch


@pytest.fixture
def thresholds_file(tmp_path, monkeypatch):
    """Write a temp threshold YAML and point the loader at it (live-reload aware)."""
    from gateway_api.pii_detection import thresholds as thr

    def _make(content: str):
        path = tmp_path / "thresholds.yaml"
        path.write_text(content, encoding="utf-8")
        monkeypatch.setenv("DETECTION_THRESHOLDS_PATH", str(path))
        thr._reset_cache_for_tests()
        return path

    yield _make
    thr._reset_cache_for_tests()


# --- Substitution / mapping (Epic 3) fixtures ------------------------------

_AES_KEY = b"0" * 32


@pytest.fixture
def enc_key() -> bytes:
    """A valid 32-byte AES-256 key for tests."""
    return _AES_KEY


@pytest.fixture
def fake_redis():
    """A fresh in-memory async Redis (no server)."""
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def make_store(fake_redis, enc_key):
    """Factory: a MappingStore backed by fakeredis + a seeded generator."""

    def _make(seed: int = 1, ttl: int = 1800):
        from gateway_api.pseudonym_generation import FakeDataGenerator
        from gateway_api.pseudonym_vault.aes_gcm_encryption import Encryptor
        from gateway_api.pseudonym_vault.mapping_store import MappingStore

        return MappingStore(
            fake_redis, Encryptor(enc_key), enc_key, ttl, FakeDataGenerator(seed=seed)
        )

    return _make


@pytest.fixture
def make_entity():
    """Factory for a DetectedEntity (offsets default to span the text)."""

    def _make(entity_type, text, *, lemma=None, case=None, metadata=None, start=0):
        from gateway_api.pii_detection.dto import DetectedEntity

        return DetectedEntity(
            entity_type=entity_type,
            start=start,
            end=start + len(text),
            score=1.0,
            text=text,
            lemma=lemma,
            case=case,
            metadata=metadata or {},
        )

    return _make
