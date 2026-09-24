from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from modules.utils.database import Database


async def register(client: Any, db: Database, settings: Any, scheduler: Any) -> None:
    scheduler.register_handler("clock_bio", lambda **_: _tick(client, settings))
    enabled = await db.get_setting("clock_bio_enabled", "0")
    if enabled == "1":
        await scheduler.add_interval("clock_bio", 60, {})


async def _tick(client: Any, settings: Any) -> None:
    from telethon import functions
    now = datetime.now(ZoneInfo(settings.timezone))
    await client(functions.AccountUpdateProfileRequest(about=f"ساعت {now:%H:%M}"))
