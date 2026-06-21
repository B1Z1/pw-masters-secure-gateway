"""Redis HASH persistence for one session's pseudonym mappings (data-model §4/§5).

The single owner of the Redis connection, the encrypted-JSON codec, and the
``fwd:/rev:/forms:/meta/corefs`` field schema. Originals are encrypted inside
values only; field names are an HMAC (forward) or the synthetic fake form
(reverse). Every write refreshes the sliding TTL (Constitution III/VIII).
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..observability.request_metrics import timed_inbound_stage
from .aes_gcm_encryption import EncryptedJsonCodec
from .session_layout import COREFS, FORMS, META, REV, SessionMeta, session_hash_key


class SessionMappingRepository:
    def __init__(
            self, redis, codec: EncryptedJsonCodec, session_ttl_seconds: int
    ) -> None:
        self._redis = redis
        self._codec = codec
        self._session_ttl_seconds = session_ttl_seconds

    # --- reads ---------------------------------------------------------------

    async def read_forward(
            self, session_id: str, forward_field_name: str
    ) -> str | None:
        encrypted_value = await self._redis.hget(
            session_hash_key(session_id), forward_field_name
        )

        if encrypted_value is None:
            return None

        return self._codec.decrypt_object(encrypted_value)

    async def read_forms(self, session_id: str, fake_base: str) -> dict | None:
        encrypted_forms = await self._redis.hget(
            session_hash_key(session_id), FORMS + fake_base
        )

        if encrypted_forms is None:
            return None

        return self._codec.decrypt_object(encrypted_forms)

    async def read_exact_reverse(self, session_id: str, fake_form: str) -> dict | None:
        encrypted_value = await self._redis.hget(
            session_hash_key(session_id), REV + fake_form
        )

        if encrypted_value is None:
            return None

        return self._codec.decrypt_object(encrypted_value)

    async def reverse_records(self, session_id: str) -> list[tuple[str, dict]]:
        """Every reverse mapping as ``(fake_form, record)`` pairs."""
        records = []
        stored = await self._redis.hgetall(session_hash_key(session_id))

        for field, encrypted_value in stored.items():
            field_name = field.decode() if isinstance(field, bytes) else field

            if field_name.startswith(REV):
                fake_form = field_name[len(REV):]

                records.append((fake_form, self._codec.decrypt_object(encrypted_value)))

        return records

    async def forms_and_reverse_indexes(
            self, session_id: str
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        """``(forms_by_base, reverse_by_form)`` — used to list all pairs."""
        forms_by_base: dict[str, dict] = {}
        reverse_by_form: dict[str, dict] = {}
        stored = await self._redis.hgetall(session_hash_key(session_id))

        for field, encrypted_value in stored.items():
            field_name = field.decode() if isinstance(field, bytes) else field

            if field_name.startswith(FORMS):
                forms_by_base[field_name[len(FORMS):]] = self._codec.decrypt_object(
                    encrypted_value
                )
            elif field_name.startswith(REV):
                reverse_by_form[field_name[len(REV):]] = self._codec.decrypt_object(
                    encrypted_value
                )

        return forms_by_base, reverse_by_form

    async def used_fake_forms(self, session_id: str) -> set[str]:
        used = set()

        for field in await self._redis.hgetall(session_hash_key(session_id)):
            field_name = field.decode() if isinstance(field, bytes) else field

            if field_name.startswith(REV):
                used.add(field_name[len(REV):])

        return used

    async def load_corefs(self, session_id: str) -> list[dict]:
        encrypted_value = await self._redis.hget(session_hash_key(session_id), COREFS)

        if encrypted_value is None:
            return []

        return self._codec.decrypt_object(encrypted_value)

    # --- writes --------------------------------------------------------------

    async def write_mapping(
            self,
            session_id: str,
            *,
            forward_field_name: str,
            fake_base: str,
            forms: dict | None,
            original_base: str,
            original_text: str,
            entity_type: str,
            normalized_key: str,
            register_coref: bool,
    ) -> None:
        fields = {forward_field_name: self._codec.encrypt_object(fake_base)}

        if forms:
            fields[FORMS + fake_base] = self._codec.encrypt_object(forms)
            for grammatical_case, fake_form in forms.items():
                fields[REV + fake_form] = self._codec.encrypt_object(
                    {
                        "orig_base": original_base,
                        "case": grammatical_case,
                        "entity_type": entity_type,
                    }
                )
        else:
            fields[REV + fake_base] = self._codec.encrypt_object(
                {
                    "orig_base": original_text,
                    "case": None,
                    "entity_type": entity_type,
                }
            )

        with timed_inbound_stage("redis_write"):
            await self._redis.hset(session_hash_key(session_id), mapping=fields)

        if register_coref:
            await self.append_coref(session_id, normalized_key, fake_base, entity_type)

        await self.bump_meta(session_id)
        await self.extend_ttl(session_id)

    async def write_exact_reverse(
            self,
            session_id: str,
            fake_form: str,
            *,
            original_text: str,
            case: str | None,
            entity_type: str,
    ) -> None:
        # The EXACT original surface for the inserted form, so restore is literal
        # (no gender-blind re-declension); lemma-based rev entries are a fallback.
        with timed_inbound_stage("redis_write"):
            await self._redis.hset(
                session_hash_key(session_id),
                REV + fake_form,
                self._codec.encrypt_object(
                    {
                        "orig_base": original_text,
                        "case": case,
                        "entity_type": entity_type,
                        "exact": True,
                    }
                ),
            )

    async def append_coref(
            self, session_id: str, normalized_key: str, fake_base: str, entity_type: str
    ) -> None:
        coref_records = await self.load_corefs(session_id)
        coref_records.append(
            {
                "lemma": normalized_key,
                "fake_base": fake_base,
                "entity_type": entity_type,
            }
        )

        with timed_inbound_stage("redis_write"):
            await self._redis.hset(
                session_hash_key(session_id),
                COREFS,
                self._codec.encrypt_object(coref_records),
            )

    async def bump_meta(self, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        encrypted_meta = await self._redis.hget(session_hash_key(session_id), META)

        if encrypted_meta is None:
            meta = SessionMeta(created_at=now, last_activity=now, entity_count=1)
        else:
            stored = self._codec.decrypt_object(encrypted_meta)
            meta = SessionMeta(
                created_at=stored["created_at"],
                last_activity=now,
                entity_count=stored.get("entity_count", 0) + 1,
                message_count=stored.get("message_count", 0),
            )

        with timed_inbound_stage("redis_write"):
            await self._redis.hset(
                session_hash_key(session_id),
                META,
                self._codec.encrypt_object(meta.to_dict()),
            )

    async def bump_message_count(self, session_id: str) -> None:
        """+1 to a successful chat round-trip count (Epic 6, FR-019/D7).

        Only when the session already has stored state (``meta`` present): a
        PII-free session has no hash, so this is a no-op and the session stays
        unmanageable (404), per the never-stored-session rule.
        """
        encrypted_meta = await self._redis.hget(session_hash_key(session_id), META)

        if encrypted_meta is None:
            return

        stored = self._codec.decrypt_object(encrypted_meta)
        meta = SessionMeta(
            created_at=stored["created_at"],
            last_activity=stored["last_activity"],
            entity_count=stored.get("entity_count", 0),
            message_count=stored.get("message_count", 0) + 1,
        )
        await self._redis.hset(
            session_hash_key(session_id),
            META,
            self._codec.encrypt_object(meta.to_dict()),
        )

    async def read_meta(self, session_id: str) -> dict | None:
        """Decrypted ``SessionMeta`` dict for the session, or ``None`` if absent."""
        encrypted_meta = await self._redis.hget(session_hash_key(session_id), META)

        if encrypted_meta is None:
            return None

        return self._codec.decrypt_object(encrypted_meta)

    async def ttl_seconds(self, session_id: str) -> int:
        """Live Redis TTL of the session hash (Redis: -2 missing, -1 no-expire)."""
        return await self._redis.ttl(session_hash_key(session_id))

    # --- lifecycle -----------------------------------------------------------

    async def extend_ttl(self, session_id: str) -> None:
        with timed_inbound_stage("redis_write"):
            await self._redis.expire(
                session_hash_key(session_id), self._session_ttl_seconds
            )

    async def delete(self, session_id: str) -> bool:
        """Delete the session hash; return whether it existed (Epic 6, FR-020)."""
        return await self._redis.delete(session_hash_key(session_id)) == 1
