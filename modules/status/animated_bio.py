from __future__ import annotations

import json
from typing import Any

from modules.utils.database import Database


async def register(client: Any, db: Database, settings: Any, scheduler: Any) -> None:
    scheduler.register_handler("animated_bio", lambda **p: _tick(client, db, **p))
    state = await db.get_rotating("bio")
    if state and state["is_active"] and state["texts"]:
        await scheduler.add_interval(
            "animated_bio",
            float(state["interval"]),
            {"texts": state["texts"]},
        )

async def _tick(client: Any, db: Database, texts: list[str]) -> None:
    state = await db.get_rotating("bio")
    if not state or not state["texts"]:
        return
    index = int(state["current_index"]) % len(texts)
    await client.edit_profile(about=texts[index])
    await db.execute(
        "UPDATE rotating_texts SET current_index = ? WHERE type = 'bio'",
        ((index + 1) % len(texts),),
    )

async def set_bio(client: Any, db: Database, scheduler: Any, texts: list[str], interval: float) -> None:
    from telethon import functions
    await db.replace_rotating_texts("bio", texts, interval, True)
    for job in scheduler.scheduler.get_jobs():
        if job.id.startswith("db:"):
            row_id = job.id[3:]
            row = await db.fetchone("SELECT task_type FROM scheduled_tasks WHERE id=?", (row_id,))
            if row and row["task_type"] == "animated_bio":
                await scheduler.remove(int(row_id))
    await scheduler.add_interval("animated_bio", interval, {"texts": texts})
    if texts:
        await client(functions.AccountUpdateProfileRequest(about=texts[0]))
