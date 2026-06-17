"""Per-session async lock registry (Epic 4 race-safety).

``MappingStore.get_or_create`` does a read-then-write with ``await`` points in
between; under concurrent requests for the SAME session + original that races and
each request mints its own fake (breaking FR-012 — same original → same fake).
This registry hands out one ``asyncio.Lock`` per session, so that critical section
runs serially per session while different sessions still proceed in parallel.

In-process only: correct for the single-worker gateway; a multi-process deployment
would need a Redis-level lock (a documented limitation, Constitution IX).
"""

from __future__ import annotations

import asyncio


class SessionLockRegistry:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, session_id: str) -> asyncio.Lock:
        """Return the (created-on-demand) lock guarding this session."""
        lock = self._locks.get(session_id)

        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock

        return lock

    def discard(self, session_id: str) -> None:
        """Forget a session's lock — called when the session is deleted."""
        self._locks.pop(session_id, None)
