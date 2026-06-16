"""Realistic Polish fake-data generation (Epic 3). Pure, stateless, seed-driven."""

from __future__ import annotations

from .dto import FakeValue
from .generator import FakeDataGenerator

__all__ = ["FakeDataGenerator", "FakeValue"]
