"""MappingStore — encrypted, reversible, expiring session mapping (contracts).

One Redis HASH per session (``session:{id}``). Original PII is AES-256-GCM
encrypted inside field VALUES only; field names are HMAC (forward) or the
synthetic fake form (reverse). Every successful op refreshes the sliding TTL.
Logs carry session_id + types/counts only, never originals/fakes (Constitution VIII).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC

from ..pii_detection.dto import DetectedEntity
from ..pseudonym_generation import FakeDataGenerator
from ..pseudonym_generation.inflection import all_forms, classify, decline
from .encryption import Encryptor, key_from_settings
from .keys import fwd_field, mapping_key
from .matching import aligned_fake, bounded_levenshtein, lemma_overlap
from .session import FORMS, META, REV, SessionMeta, session_hash_key

logger = logging.getLogger("gateway_api")

_NAME_TYPES = frozenset({"PERSON", "LOCATION"})
_COREFS = "corefs"  # one field: enc(json[{lemma, fake_base, entity_type}])
_MAX_GEN_ATTEMPTS = 4


def _titlecase(lemma: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in lemma.split())


class MappingStore:
    def __init__(self, redis, encryptor, key_bytes, ttl, generator):
        self._redis = redis
        self._enc: Encryptor = encryptor
        self._key: bytes = key_bytes
        self._ttl: int = ttl
        self._gen: FakeDataGenerator = generator

    # --- encryption helpers --------------------------------------------------

    def _seal(self, obj) -> bytes:
        return self._enc.encrypt(json.dumps(obj, ensure_ascii=False).encode())

    def _open(self, blob: bytes):
        return json.loads(self._enc.decrypt(blob).decode())

    # --- public API ----------------------------------------------------------

    async def get_or_create(self, session_id: str, entity: DetectedEntity) -> str:
        hkey = session_hash_key(session_id)
        is_name = entity.entity_type in _NAME_TYPES
        case = entity.case if is_name else None
        mkey = mapping_key(entity.entity_type, entity.text, entity.lemma)
        fwd = fwd_field(self._key, entity.entity_type, mkey)

        cached = await self._redis.hget(hkey, fwd)
        if cached is not None:
            fake_base = self._open(cached)
            await self.extend_ttl(session_id)
            return await self._render(hkey, fake_base, case)

        if is_name:
            reused = await self._try_coreference(hkey, entity, mkey, fwd, case)
            if reused is not None:
                return reused

        return await self._generate_and_store(hkey, entity, mkey, fwd, case)

    async def get_original(self, session_id: str, fake_form: str) -> dict | None:
        """Return ``{orig_base, case, entity_type}`` for a fake form, or None."""
        hkey = session_hash_key(session_id)
        exact = await self._redis.hget(hkey, REV + fake_form)
        if exact is not None:
            await self.extend_ttl(session_id)
            return self._open(exact)
        # bounded fuzzy over rev field names (research D8)
        best, best_d = None, 99
        for field, blob in (await self._redis.hgetall(hkey)).items():
            name = field.decode() if isinstance(field, bytes) else field
            if not name.startswith(REV):
                continue
            d = bounded_levenshtein(fake_form, name[len(REV) :])
            if d is not None and d < best_d:
                best, best_d = blob, d
        if best is not None:
            await self.extend_ttl(session_id)
            return self._open(best)
        return None

    async def get_all_mappings(self, session_id: str) -> list[dict]:
        """All original↔fake pairs for reviewer inspection (FR-011).

        Reconstructs one pair per mapping from the ``forms`` index (name types,
        whose fake base is the field suffix) plus the bare ``rev`` records
        (non-inflecting types) — robust even when a fake is indeclinable and all
        cases collapse onto one rev field.
        """
        hkey = session_hash_key(session_id)
        forms_by_base: dict[str, dict] = {}
        rev_by_form: dict[str, dict] = {}
        for field, blob in (await self._redis.hgetall(hkey)).items():
            name = field.decode() if isinstance(field, bytes) else field
            if name.startswith(FORMS):
                forms_by_base[name[len(FORMS) :]] = self._open(blob)
            elif name.startswith(REV):
                rev_by_form[name[len(REV) :]] = self._open(blob)

        out, seen = [], set()

        def _add(entity_type, original, fake):
            key = (entity_type, original, fake)
            if key not in seen:
                seen.add(key)
                out.append(
                    {"entity_type": entity_type, "original": original, "fake": fake}
                )

        # name-type mappings: fake_base = the forms-field suffix
        for fake_base, fmap in forms_by_base.items():
            rec = next(
                (rev_by_form[f] for f in fmap.values() if f in rev_by_form), None
            )
            if rec is not None:
                _add(rec["entity_type"], rec["orig_base"], fake_base)
        # non-inflecting mappings: one bare rev per fake
        for fake_form, rec in rev_by_form.items():
            if rec["entity_type"] not in _NAME_TYPES:
                _add(rec["entity_type"], rec["orig_base"], fake_form)

        if out:
            await self.extend_ttl(session_id)
        return out

    async def restore_text(self, session_id: str, text: str) -> str:
        """Replace every fake form in ``text`` with its original (FR-022).

        Longest-first + word-boundary aware so a fake never partially clobbers
        another; case-aware for PERSON/LOCATION (decline the original to the fake
        form's case). Exact rev match drives this; ``get_original`` adds fuzzy.
        """
        import re

        hkey = session_hash_key(session_id)
        forms: list[tuple[str, dict]] = []
        for field, blob in (await self._redis.hgetall(hkey)).items():
            name = field.decode() if isinstance(field, bytes) else field
            if name.startswith(REV):
                forms.append((name[len(REV) :], self._open(blob)))
        if not forms:
            return text
        forms.sort(key=lambda x: len(x[0]), reverse=True)
        for fake_form, rec in forms:
            original = self._restore_surface(rec)
            text = re.sub(
                rf"(?<!\w){re.escape(fake_form)}(?!\w)",
                lambda _m, _o=original: _o,
                text,
            )
        await self.extend_ttl(session_id)
        return text

    def _restore_surface(self, rec: dict) -> str:
        ob = rec["orig_base"]
        case = rec.get("case")
        if rec["entity_type"] in _NAME_TYPES and case and case != "nom":
            kind = "city" if rec["entity_type"] == "LOCATION" else "person"
            return " ".join(
                decline(t, classify(t, None, kind=kind), case) for t in ob.split()
            )
        return ob

    async def delete_session(self, session_id: str) -> None:
        await self._redis.delete(session_hash_key(session_id))

    async def extend_ttl(self, session_id: str) -> None:
        await self._redis.expire(session_hash_key(session_id), self._ttl)

    # --- internals -----------------------------------------------------------

    async def _render(self, hkey: str, fake_base: str, case: str | None) -> str:
        if not case or case == "nom":
            return fake_base
        forms_blob = await self._redis.hget(hkey, FORMS + fake_base)
        if forms_blob is None:
            return fake_base
        return self._open(forms_blob).get(case, fake_base)

    async def _used_fakes(self, hkey: str) -> set[str]:
        used = set()
        for field in await self._redis.hgetall(hkey):
            name = field.decode() if isinstance(field, bytes) else field
            if name.startswith(REV):
                used.add(name[len(REV) :])
        return used

    async def _load_corefs(self, hkey: str) -> list[dict]:
        blob = await self._redis.hget(hkey, _COREFS)
        return self._open(blob) if blob is not None else []

    async def _try_coreference(self, hkey, entity, mkey, fwd, case) -> str | None:
        corefs = await self._load_corefs(hkey)
        matches = [
            c
            for c in corefs
            if c["entity_type"] == entity.entity_type
            and lemma_overlap(mkey, c["lemma"])
        ]
        distinct = {m["fake_base"] for m in matches}
        if len(distinct) != 1:
            return None  # 0 → new; ≥2 ambiguous → new person (clarification Q2)
        matched = matches[0]
        fake_base = aligned_fake(mkey, matched["lemma"], matched["fake_base"])
        forms = all_forms(fake_base, classify(fake_base, entity.metadata.get("gender")))
        await self._write_mapping(
            hkey, entity, mkey, fwd, fake_base, forms, register_coref=True
        )
        return forms.get(case or "nom", fake_base)

    async def _generate_and_store(self, hkey, entity, mkey, fwd, case) -> str:
        used = await self._used_fakes(hkey)
        fake = self._gen.generate(entity)
        for _ in range(_MAX_GEN_ATTEMPTS - 1):
            candidates = [fake.base, *(fake.forms.values() if fake.forms else [])]
            if not any(c in used for c in candidates):
                break
            fake = self._gen.generate(entity)
        else:
            fake = self._force_unique(fake, used)
        await self._write_mapping(
            hkey,
            entity,
            mkey,
            fwd,
            fake.base,
            fake.forms,
            register_coref=entity.entity_type in _NAME_TYPES,
        )
        if entity.entity_type in _NAME_TYPES and fake.forms:
            return fake.forms.get(case or "nom", fake.base)
        return fake.base

    def _force_unique(self, fake, used: set[str]):
        """Deterministic fallback when retries still collide (research D6)."""
        if fake.base.isdigit():
            n = 1
            while (cand := fake.base[: -len(str(n))] + str(n)) in used:
                n += 1
            return fake.model_copy(update={"base": cand, "forms": None})
        # names/other: append a re-roll suffix only as a last resort
        suffix = 2
        while f"{fake.base}{suffix}" in used:
            suffix += 1
        return fake.model_copy(update={"base": f"{fake.base}{suffix}", "forms": None})

    async def _write_mapping(
        self, hkey, entity, mkey, fwd, fake_base, forms, *, register_coref
    ):
        orig_base = _titlecase(entity.lemma) if entity.lemma else entity.text
        mapping = {fwd: self._seal(fake_base)}
        if forms:
            mapping[FORMS + fake_base] = self._seal(forms)
            for c, form in forms.items():
                mapping[REV + form] = self._seal(
                    {
                        "orig_base": orig_base,
                        "case": c,
                        "entity_type": entity.entity_type,
                    }
                )
        else:
            mapping[REV + fake_base] = self._seal(
                {
                    "orig_base": entity.text,
                    "case": None,
                    "entity_type": entity.entity_type,
                }
            )
        await self._redis.hset(hkey, mapping=mapping)

        if register_coref:
            corefs = await self._load_corefs(hkey)
            corefs.append(
                {
                    "lemma": mkey,
                    "fake_base": fake_base,
                    "entity_type": entity.entity_type,
                }
            )
            await self._redis.hset(hkey, _COREFS, self._seal(corefs))

        await self._bump_meta(hkey)
        await self.extend_ttl(session_id=hkey.split(":", 1)[1])

    async def _bump_meta(self, hkey: str) -> None:
        from datetime import datetime

        now = datetime.now(UTC).isoformat()
        blob = await self._redis.hget(hkey, META)
        if blob is None:
            meta = SessionMeta(created_at=now, last_activity=now, entity_count=1)
        else:
            d = self._open(blob)
            meta = SessionMeta(
                created_at=d["created_at"],
                last_activity=now,
                entity_count=d.get("entity_count", 0) + 1,
                message_count=d.get("message_count", 0),
            )
        await self._redis.hset(hkey, META, self._seal(meta.to_dict()))


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
