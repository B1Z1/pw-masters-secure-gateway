"""SessionLockRegistry: stable per-session locks + serialization."""

from __future__ import annotations

import asyncio

from gateway_api.pseudonym_vault.session_lock_registry import SessionLockRegistry


def test_same_session_returns_same_lock():
    registry = SessionLockRegistry()
    assert registry.lock("s") is registry.lock("s")


def test_distinct_sessions_get_distinct_locks():
    registry = SessionLockRegistry()
    assert registry.lock("a") is not registry.lock("b")


def test_discard_forgets_lock():
    registry = SessionLockRegistry()
    first = registry.lock("s")
    registry.discard("s")
    assert registry.lock("s") is not first


async def test_lock_serializes_critical_section():
    registry = SessionLockRegistry()
    order = []

    async def worker(worker_id):
        async with registry.lock("s"):
            order.append(("enter", worker_id))
            await asyncio.sleep(0)  # yield — would interleave without the lock
            order.append(("exit", worker_id))

    await asyncio.gather(*(worker(i) for i in range(5)))

    # each enter is immediately followed by ITS OWN exit (no interleaving)
    for index in range(0, len(order), 2):
        assert order[index][0] == "enter"
        assert order[index + 1] == ("exit", order[index][1])
