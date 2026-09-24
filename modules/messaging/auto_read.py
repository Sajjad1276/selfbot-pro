from __future__ import annotations

import asyncio
from typing import Any


def register(client: Any, db: Any) -> None:
    from telethon import events

    @client.on(events.NewMessage(incoming=True))
    async def mark_read(event: Any) -> None:
        if not event.is_private:
            return
        if await db.get_setting("auto_read", "0") != "1":
            return
        delay = float(await db.get_setting("auto_read_delay", "1.0") or 1.0)
        await asyncio.sleep(max(0.0, min(delay, 30.0)))
        try:
            await client.send_read_acknowledge(event.chat_id)
        except Exception:
            return
