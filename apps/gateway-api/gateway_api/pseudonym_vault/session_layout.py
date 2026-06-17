"""Session metadata + Redis field prefixes (data-model §4/§5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

# Redis HASH field prefixes (one hash per session: session:{id}).
FWD = "fwd:"  # fwd:{hmac}        -> enc(fake_base)
REV = "rev:"  # rev:{fake_form}   -> enc(json{orig_base, case, entity_type})
FORMS = "forms:"  # forms:{fake_base} -> enc(json{case: fake_form, ...})
META = "meta"  # meta              -> enc(json SessionMeta)
COREFS = "corefs"  # corefs            -> enc(json[{lemma, fake_base, entity_type}])


def session_hash_key(session_id: str) -> str:
    return f"session:{session_id}"


@dataclass
class SessionMeta:
    created_at: str
    last_activity: str
    entity_count: int = 0
    message_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)
