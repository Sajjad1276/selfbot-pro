from __future__ import annotations

from typing import Any


async def get_group_info(client: Any, entity: Any) -> dict[str, Any]:
    chat = await client.get_entity(entity)
    return {
        "id": chat.id,
        "title": getattr(chat, "title", None),
        "username": getattr(chat, "username", None),
        "megagroup": bool(getattr(chat, "megagroup", False)),
        "broadcast": bool(getattr(chat, "broadcast", False)),
    }


async def list_participants(client: Any, entity: Any, limit: int = 100) -> list[dict[str, Any]]:
    result=[]
    async for user in client.iter_participants(entity, limit=limit):
        result.append({
            "id": user.id,
            "username": getattr(user, "username", None),
            "name": " ".join(x for x in [user.first_name, user.last_name] if x),
        })
    return result
