from __future__ import annotations

from typing import Any

from modules.utils.database import Database


async def register(client: Any, db: Database, settings: Any, scheduler: Any) -> None:
    scheduler.register_handler("rotating_name", lambda **p: _tick(client, db, **p))
    state = await db.get_rotating("name")
    if state and state["is_active"] and state["texts"]:
        await scheduler.add_interval("rotating_name", float(state["interval"]), {"texts": state["texts"]})

async def _tick(client: Any, db: Database, texts: list[str]) -> None:
    from telethon import functions
    state = await db.get_rotating("name")
    if not state:
        return
    index = int(state["current_index"]) % len(texts)
    await client(functions.AccountUpdateProfileRequest(first_name=texts[index]))
    await db.execute("UPDATE rotating_texts SET current_index=? WHERE type='name'", ((index + 1) % len(texts),))

async def set_name(client: Any, db: Database, scheduler: Any, texts: list[str], interval: float) -> None:
    await db.replace_rotating_texts("name", texts, interval, True)
    await scheduler.add_interval("rotating_name", interval, {"texts": texts})
