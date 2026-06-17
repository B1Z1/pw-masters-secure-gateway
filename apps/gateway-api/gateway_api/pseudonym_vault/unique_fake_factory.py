"""Collision-free fake minting (research D6). Pure with respect to Redis."""

from __future__ import annotations

from ..pii_detection.dto import DetectedEntity
from ..pseudonym_generation import FakeDataGenerator
from ..pseudonym_generation.dto import FakeValue

MAX_GENERATION_ATTEMPTS = 4


class UniqueFakeFactory:
    """Generate a fake whose every surface form is unused in the session.

    Retries the generator a few times, then falls back to a deterministic suffix
    so minting always terminates with a value distinct from those already used.
    """

    def __init__(self, generator: FakeDataGenerator) -> None:
        self._generator = generator

    def mint(self, entity: DetectedEntity, used_fake_forms: set[str]) -> FakeValue:
        fake = self._generator.generate(entity)

        for _ in range(MAX_GENERATION_ATTEMPTS - 1):
            candidate_forms = [fake.base, *(fake.forms.values() if fake.forms else [])]

            if not any(form in used_fake_forms for form in candidate_forms):
                return fake

            fake = self._generator.generate(entity)

        return self._force_unique(fake, used_fake_forms)

    def _force_unique(self, fake: FakeValue, used_fake_forms: set[str]) -> FakeValue:
        if fake.base.isdigit():
            suffix_number = 1

            while (
                candidate := fake.base[: -len(str(suffix_number))] + str(suffix_number)
            ) in used_fake_forms:
                suffix_number += 1

            return fake.model_copy(update={"base": candidate, "forms": None})

        # names/other: append a re-roll suffix only as a last resort
        suffix = 2

        while f"{fake.base}{suffix}" in used_fake_forms:
            suffix += 1

        return fake.model_copy(update={"base": f"{fake.base}{suffix}", "forms": None})
