from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class ActionPacer:
    """Bounded action pacing to prevent accidental request bursts."""

    def __init__(self, default_limit: int = 20) -> None:
        self.default_limit = default_limit
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _trim(self, key: str, window: float) -> None:
        cutoff = time.monotonic() - window
        q = self._events[key]
        while q and q[0] < cutoff:
            q.popleft()

    async def wait_turn(self, key: str = "global", limit: int | None = None, window: float = 60.0) -> None:
        cap = limit or self.default_limit
        async with self._locks[key]:
            while True:
                self._trim(key, window)
                if len(self._events[key]) < cap:
                    self._events[key].append(time.monotonic())
                    return
                await asyncio.sleep(max(0.1, window - (time.monotonic() - self._events[key][0])))
