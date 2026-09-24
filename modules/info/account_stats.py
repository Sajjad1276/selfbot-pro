from __future__ import annotations

from collections.abc import Iterable
from typing import Any


async def collect_account_stats(client: Any) -> dict[str, int | str | None]:
    me = await client.get_me()
    dialogs = [dialog async for dialog in client.iter_dialogs()]
    contacts = await client.get_contacts()
    groups = sum(1 for d in dialogs if d.is_group)
    channels = sum(1 for d in dialogs if d.is_channel)
    return {
        "id": me.id,
        "username": me.username,
        "name": " ".join(x for x in [me.first_name, me.last_name] if x),
        "groups": groups,
        "channels": channels,
        "contacts": len(contacts.users) if hasattr(contacts, "users") else 0,
    }


async def recent_message_count(client: Any, chat_id: int, limit: int = 1000) -> int:
    count = 0
    async for _ in client.iter_messages(chat_id, limit=limit):
        count += 1
    return count
