from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


async def register(client: Any, db: Any, settings: Any, scheduler: Any) -> None:
    scheduler.register_handler("time_bio", lambda **p: _tick(client, **p))


async def _tick(client: Any, zones: list[str]) -> None:
    from telethon import functions
    values = []
    for zone in zones:
        try:
            values.append(f"{zone} {datetime.now(ZoneInfo(zone)):%H:%M}")
        except Exception:
            continue
    if values:
        await client(functions.AccountUpdateProfileRequest(about=" | ".join(values)))


async def set_world_clock(client: Any, scheduler: Any, zones: list[str], interval: int = 60) -> None:
    await scheduler.add_interval("time_bio", interval, {"zones": zones})
