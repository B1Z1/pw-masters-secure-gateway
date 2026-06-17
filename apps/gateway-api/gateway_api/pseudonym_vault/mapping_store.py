"""MappingStore — encrypted, reversible, expiring session mapping (contracts).

Thin orchestration over focused collaborators: an encrypted-JSON codec and a
Redis repository (persistence + field schema), a coreference resolver (name
reuse), a unique-fake factory (collision-free minting), and an original-surface
restorer (case-aware reversal). Same original → same fake within a session;
ambiguous surname-only → a new person. Logs carry session_id + types/counts
only, never originals/fakes (Constitution VIII).
"""

from __future__ import annotations

import re

from ..pii_detection.dto import DetectedEntity
from ..pseudonym_generation import FakeDataGenerator
from ..pseudonym_generation.inflection import all_forms, classify
from .aes_gcm_encryption import EncryptedJsonCodec, Encryptor, key_from_settings
from .coreference_matching import CoreferenceResolver, bounded_levenshtein
from .fuzzy_restoration import FuzzyNameRestorer
from .mapping_keys import fwd_field, mapping_key
from .original_restoration import OriginalSurfaceRestorer
from .session_lock_registry import SessionLockRegistry
from .session_mapping_repository import SessionMappingRepository
from .unique_fake_factory import UniqueFakeFactory

_NAME_TYPES = frozenset({"PERSON", "LOCATION"})


class MappingStore:
    def __init__(self, redis, encryptor, key_bytes, ttl, generator):
        self._encryption_key: bytes = key_bytes
        self._repository = SessionMappingRepository(
            redis, EncryptedJsonCodec(encryptor), ttl
        )
        self._coreference_resolver = CoreferenceResolver()
        self._fake_factory = UniqueFakeFactory(generator)
        self._surface_restorer = OriginalSurfaceRestorer()
        self._fuzzy_restorer = FuzzyNameRestorer()
        self._session_locks = SessionLockRegistry()

    # --- public API ----------------------------------------------------------

    async def get_or_create(self, session_id: str, entity: DetectedEntity) -> str:
        # Serialize per session: concurrent requests for the SAME original must not
        # each mint a different fake (a read-then-write race would break FR-012 —
        # same original → same fake). See SessionLockRegistry for the in-process /
        # single-worker limitation.
        async with self._session_locks.lock(session_id):
            return await self._substitute(session_id, entity)

    async def _substitute(self, session_id: str, entity: DetectedEntity) -> str:
        is_inflecting_name = entity.entity_type in _NAME_TYPES
        case = entity.case if is_inflecting_name else None
        normalized_key = mapping_key(entity.entity_type, entity.text, entity.lemma)
        forward_field_name = fwd_field(
            self._encryption_key, entity.entity_type, normalized_key
        )

        cached_fake_base = await self._repository.read_forward(
            session_id, forward_field_name
        )

        if cached_fake_base is not None:
            fake_form = await self._render(session_id, cached_fake_base, case)
        else:
            fake_form = await self._reuse_or_mint(
                session_id, entity, normalized_key, forward_field_name, case
            )

        if is_inflecting_name:
            # Record the EXACT original surface for the form actually inserted, so
            # restore is literal; pre-written lemma-based rev entries are a fallback.
            await self._repository.write_exact_reverse(
                session_id,
                fake_form,
                original_text=entity.text,
                case=entity.case,
                entity_type=entity.entity_type,
            )

        await self.extend_ttl(session_id)

        return fake_form

    async def get_original(self, session_id: str, fake_form: str) -> dict | None:
        """Return ``{orig_base, case, entity_type}`` for a fake form, or None."""
        exact_record = await self._repository.read_exact_reverse(session_id, fake_form)

        if exact_record is not None:
            await self.extend_ttl(session_id)

            return exact_record

        # bounded fuzzy over reverse field names (research D8)
        best_record, best_distance = None, 99

        for stored_form, reverse_record in await self._repository.reverse_records(
                session_id
        ):
            distance = bounded_levenshtein(fake_form, stored_form)

            if distance is not None and distance < best_distance:
                best_record, best_distance = reverse_record, distance

        if best_record is not None:
            await self.extend_ttl(session_id)

            return best_record

        return None

    async def get_all_mappings(self, session_id: str) -> list[dict]:
        """All original↔fake pairs for reviewer inspection (FR-011).

        Reconstructs one pair per mapping from the ``forms`` index (name types,
        whose fake base is the field suffix) plus the bare ``rev`` records
        (non-inflecting types) — robust even when a fake is indeclinable and all
        cases collapse onto one rev field.
        """
        (
            forms_by_base,
            reverse_by_form,
        ) = await self._repository.forms_and_reverse_indexes(session_id)
        pairs, seen = [], set()

        def add_pair(entity_type, original, fake):
            key = (entity_type, original, fake)
            if key not in seen:
                seen.add(key)
                pairs.append(
                    {"entity_type": entity_type, "original": original, "fake": fake}
                )

        # name-type mappings: fake_base = the forms-field suffix
        for fake_base, forms_by_case in forms_by_base.items():
            reverse_record = next(
                (
                    reverse_by_form[fake_form]
                    for fake_form in forms_by_case.values()
                    if fake_form in reverse_by_form
                ),
                None,
            )
            if reverse_record is not None:
                add_pair(
                    reverse_record["entity_type"],
                    reverse_record["orig_base"],
                    fake_base,
                )
        # non-inflecting mappings: one bare rev per fake
        for fake_form, reverse_record in reverse_by_form.items():
            if reverse_record["entity_type"] not in _NAME_TYPES:
                add_pair(
                    reverse_record["entity_type"],
                    reverse_record["orig_base"],
                    fake_form,
                )

        if pairs:
            await self.extend_ttl(session_id)

        return pairs

    async def restore_text(
            self, session_id: str, text: str, fuzzy: bool = False
    ) -> str:
        """Replace every fake form in ``text`` with its original (FR-022).

        Longest-first + word-boundary aware so a fake never partially clobbers
        another; case-aware for PERSON/LOCATION (decline the original to the fake
        form's case). The exact + inflection pass below is unchanged.

        ``fuzzy=True`` (Epic 4, FR-004/FR-008) adds a bounded, PERSON/LOCATION-only
        fuzzy fallback over the tokens the exact pass did not replace; default
        ``False`` keeps the Epic 3 behaviour byte-identical (``/v1/depseudonymize``).
        """
        reverse_records = await self._repository.reverse_records(session_id)

        if not reverse_records:
            return text

        reverse_records.sort(key=lambda item: len(item[0]), reverse=True)

        for fake_form, reverse_record in reverse_records:
            original = self._surface_restorer.restore_surface(reverse_record)
            text = re.sub(
                rf"(?<!\w){re.escape(fake_form)}(?!\w)",
                lambda _match, _original=original: _original,
                text,
            )

        if fuzzy:
            text = await self._fuzzy_restore_names(session_id, text)

        await self.extend_ttl(session_id)

        return text

    async def _fuzzy_restore_names(self, session_id: str, text: str) -> str:
        """Outbound fuzzy fallback over PERSON/LOCATION fakes (Epic 4).

        Builds one name record per fake base from the ``forms`` index (the stored
        per-case fake surfaces) + the ``rev`` records (the nominative original and
        entity type), scoped to PERSON/LOCATION, then delegates the bounded,
        prefix-anchored token pass to ``FuzzyNameRestorer``.
        """
        (
            forms_by_base,
            reverse_by_form,
        ) = await self._repository.forms_and_reverse_indexes(session_id)
        name_records = []

        for fake_base, forms_by_case in forms_by_base.items():
            reverse_record = next(
                (
                    reverse_by_form[fake_form]
                    for fake_form in forms_by_case.values()
                    if fake_form in reverse_by_form
                ),
                None,
            )

            if (
                    reverse_record is None
                    or reverse_record["entity_type"] not in _NAME_TYPES
            ):
                continue

            name_records.append(
                {
                    "entity_type": reverse_record["entity_type"],
                    "orig_base": self._surface_restorer.titlecase(
                        reverse_record["orig_base"]
                    ),
                    "fake_base": fake_base,
                    "fake_forms": list(forms_by_case.values()),
                }
            )

        if not name_records:
            return text

        return self._fuzzy_restorer.restore(text, name_records)

    async def delete_session(self, session_id: str) -> None:
        await self._repository.delete(session_id)
        self._session_locks.discard(session_id)

    async def extend_ttl(self, session_id: str) -> None:
        await self._repository.extend_ttl(session_id)

    # --- internals -----------------------------------------------------------

    async def _render(self, session_id: str, fake_base: str, case: str | None) -> str:
        if not case or case == "nom":
            return fake_base

        forms = await self._repository.read_forms(session_id, fake_base)

        return self._surface_restorer.render_case(fake_base, forms, case)

    async def _reuse_or_mint(
            self, session_id, entity, normalized_key, forward_field_name, case
    ) -> str:
        if entity.entity_type in _NAME_TYPES:
            reused_form = await self._reuse_coreferent(
                session_id, entity, normalized_key, forward_field_name, case
            )

            if reused_form is not None:
                return reused_form

        return await self._mint_new(
            session_id, entity, normalized_key, forward_field_name, case
        )

    async def _reuse_coreferent(
            self, session_id, entity, normalized_key, forward_field_name, case
    ) -> str | None:
        coref_records = await self._repository.load_corefs(session_id)
        fake_base = self._coreference_resolver.resolve(
            entity.entity_type, normalized_key, coref_records
        )

        if fake_base is None:
            return None

        forms = all_forms(fake_base, classify(fake_base, entity.metadata.get("gender")))

        await self._write_mapping(
            session_id,
            entity,
            normalized_key,
            forward_field_name,
            fake_base,
            forms,
            register_coref=True,
        )

        return forms.get(case or "nom", fake_base)

    async def _mint_new(
            self, session_id, entity, normalized_key, forward_field_name, case
    ) -> str:
        used_fake_forms = await self._repository.used_fake_forms(session_id)
        fake = self._fake_factory.mint(entity, used_fake_forms)

        await self._write_mapping(
            session_id,
            entity,
            normalized_key,
            forward_field_name,
            fake.base,
            fake.forms,
            register_coref=entity.entity_type in _NAME_TYPES,
        )

        if entity.entity_type in _NAME_TYPES and fake.forms:
            return fake.forms.get(case or "nom", fake.base)

        return fake.base

    async def _write_mapping(
            self,
            session_id,
            entity,
            normalized_key,
            forward_field_name,
            fake_base,
            forms,
            *,
            register_coref,
    ) -> None:
        original_base = (
            self._surface_restorer.titlecase(entity.lemma)
            if entity.lemma
            else entity.text
        )

        await self._repository.write_mapping(
            session_id,
            forward_field_name=forward_field_name,
            fake_base=fake_base,
            forms=forms,
            original_base=original_base,
            original_text=entity.text,
            entity_type=entity.entity_type,
            normalized_key=normalized_key,
            register_coref=register_coref,
        )


_store: MappingStore | None = None


def get_mapping_store() -> MappingStore | None:
    """Process-wide MappingStore singleton over the Epic 1 Redis client."""
    global _store
    if _store is not None:
        return _store
    from ..config import get_settings
    from ..dependencies import get_redis_client

    redis = get_redis_client()

    if redis is None:
        return None

    settings = get_settings()
    _store = MappingStore(
        redis=redis,
        encryptor=Encryptor(key_from_settings(settings)),
        key_bytes=key_from_settings(settings),
        ttl=settings.redis_session_ttl,
        generator=FakeDataGenerator(),
    )

    return _store
