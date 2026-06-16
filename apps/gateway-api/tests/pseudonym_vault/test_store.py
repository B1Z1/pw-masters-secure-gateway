"""MappingStore: bidirectional, consistency, lifecycle, at-rest (T018/T032/T045)."""

from __future__ import annotations

from gateway_api.pseudonym_generation.dto import FakeValue
from gateway_api.pseudonym_vault.encryption import Encryptor
from gateway_api.pseudonym_vault.store import MappingStore

_PESEL = {"gender": "male"}


# --- US1: core bidirectional mapping ----------------------------------------


async def test_bidirectional(make_store, make_entity):
    store = make_store()
    e = make_entity("PESEL", "90010112345", metadata=_PESEL)
    fake = await store.get_or_create("s", e)
    assert fake and fake != "90010112345"
    rec = await store.get_original("s", fake)
    assert rec["orig_base"] == "90010112345"
    assert rec["entity_type"] == "PESEL"


async def test_idempotent_same_original(make_store, make_entity):
    store = make_store()
    e = make_entity("PESEL", "90010112345", metadata=_PESEL)
    assert await store.get_or_create("s", e) == await store.get_or_create("s", e)


# --- US2: consistency / coreference / collisions ----------------------------


async def test_full_name_then_surname_only(make_store, make_entity):
    store = make_store(seed=7)
    full = await store.get_or_create(
        "s", make_entity("PERSON", "Jan Kowalski", lemma="Jan Kowalski", case="nom")
    )
    surname = await store.get_or_create(
        "s", make_entity("PERSON", "Kowalski", lemma="Kowalski", case="nom")
    )
    assert surname == full.split()[-1]  # same fake person, surname part


async def test_distinct_people_shared_root(make_store, make_entity):
    store = make_store(seed=7)
    a = await store.get_or_create(
        "s", make_entity("PERSON", "Jan Kowalski", lemma="Jan Kowalski", case="nom")
    )
    b = await store.get_or_create(
        "s", make_entity("PERSON", "Anna Kowalska", lemma="Anna Kowalska", case="nom")
    )
    assert a != b


async def test_ambiguous_surname_becomes_new_person(make_store, make_entity):
    store = make_store(seed=7)
    await store.get_or_create(
        "s", make_entity("PERSON", "Jan Kowalski", lemma="Jan Kowalski", case="nom")
    )
    await store.get_or_create(
        "s", make_entity("PERSON", "Adam Kowalski", lemma="Adam Kowalski", case="nom")
    )
    surname = await store.get_or_create(
        "s", make_entity("PERSON", "Kowalski", lemma="Kowalski", case="nom")
    )
    # mapped consistently to its own entry (never guesses between the two)
    assert (await store.get_original("s", surname)) is not None
    assert (
        await store.get_or_create(
            "s", make_entity("PERSON", "Kowalski", lemma="Kowalski", case="nom")
        )
        == surname
    )


async def test_separator_variants_one_fake(make_store, make_entity):
    store = make_store()
    a = await store.get_or_create(
        "s", make_entity("PESEL", "90010112345", metadata=_PESEL)
    )
    b = await store.get_or_create(
        "s", make_entity("PESEL", "900-101-123-45", metadata=_PESEL)
    )
    assert a == b


async def test_same_literal_two_types_independent(make_store, make_entity):
    store = make_store()
    a = await store.get_or_create(
        "s", make_entity("PESEL", "1234512345", metadata=_PESEL)
    )
    b = await store.get_or_create("s", make_entity("NIP", "1234512345"))
    assert a != b


async def test_collision_free(fake_redis, enc_key, make_entity):
    class _StubGen:
        def __init__(self, values):
            self._values = list(values)
            self._i = 0

        def generate(self, entity):
            v = self._values[min(self._i, len(self._values) - 1)]
            self._i += 1
            return FakeValue(entity_type=entity.entity_type, base=v)

    gen = _StubGen(["55501112233", "55501112233", "55509998877"])
    store = MappingStore(fake_redis, Encryptor(enc_key), enc_key, 1800, gen)
    a = await store.get_or_create("s", make_entity("NIP", "1111111111"))
    b = await store.get_or_create("s", make_entity("NIP", "2222222222"))
    assert a != b  # collision retried → unique fake


# --- US4: lifecycle + at-rest security --------------------------------------


async def test_encrypted_at_rest_no_pii_in_names_or_values(
    make_store, make_entity, fake_redis
):
    store = make_store(seed=7)
    await store.get_or_create(
        "s", make_entity("PERSON", "Jan Kowalski", lemma="Jan Kowalski", case="nom")
    )
    raw = await fake_redis.hgetall("session:s")
    assert raw  # something was written
    assert all(b"Kowalski" not in v for v in raw.values())  # originals encrypted
    assert all(b"Kowalski" not in k for k in raw)  # no PII in field names


async def test_ttl_set_and_sliding(make_store, make_entity, fake_redis):
    store = make_store(ttl=1800)
    await store.get_or_create("s", make_entity("PESEL", "90010112345", metadata=_PESEL))
    assert 0 < (await fake_redis.ttl("session:s")) <= 1800
    await store.extend_ttl("s")
    assert 0 < (await fake_redis.ttl("session:s")) <= 1800


async def test_delete_removes_all(make_store, make_entity):
    store = make_store()
    await store.get_or_create("s", make_entity("PESEL", "90010112345", metadata=_PESEL))
    await store.delete_session("s")
    assert await store.get_all_mappings("s") == []


async def test_get_all_mappings_lists_pairs(make_store, make_entity):
    store = make_store()
    await store.get_or_create("s", make_entity("PESEL", "90010112345", metadata=_PESEL))
    mappings = await store.get_all_mappings("s")
    assert len(mappings) == 1
    assert mappings[0]["entity_type"] == "PESEL"
    assert mappings[0]["original"] == "90010112345"


async def test_missing_session_is_empty(make_store):
    assert await make_store().get_all_mappings("never-existed") == []


async def test_restore_round_trip_with_inflection(make_store, make_entity):
    store = make_store(seed=7)
    nom = await store.get_or_create(
        "s", make_entity("PERSON", "Jan Kowalski", lemma="Jan Kowalski", case="nom")
    )
    gen = await store.get_or_create(
        "s", make_entity("PERSON", "Kowalskiego", lemma="Kowalski", case="gen")
    )
    restored = await store.restore_text("s", f"{nom} oraz {gen}")
    assert restored == "Jan Kowalski oraz Kowalskiego"


async def test_listing_includes_entity_seen_only_in_oblique_case(
    make_store, make_entity
):
    # A LOCATION first seen in the locative ("Krakowie") must still be listed
    # by its base pair — even if the fake happens to be indeclinable.
    store = make_store(seed=7)
    await store.get_or_create(
        "s", make_entity("LOCATION", "Krakowie", lemma="Kraków", case="loc")
    )
    listed = await store.get_all_mappings("s")
    assert any(
        m["entity_type"] == "LOCATION" and m["original"] == "Kraków" for m in listed
    )


async def test_round_trip_exact_for_female_consonant_surname(make_store, make_entity):
    # "Anną Nowak" (instrumental; a woman's consonant surname does NOT decline)
    # must restore to exactly "Anną Nowak" — not the gender-blind "Anną Nowakiem".
    store = make_store(seed=3)
    fake = await store.get_or_create(
        "s", make_entity("PERSON", "Anną Nowak", lemma="Anna Nowak", case="ins")
    )
    restored = await store.restore_text("s", f"Spotkanie z {fake}.")
    assert restored == "Spotkanie z Anną Nowak."
