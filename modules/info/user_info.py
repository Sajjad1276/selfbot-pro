from __future__ import annotations

from typing import Any


async def get_user_info(client: Any, entity: Any) -> dict[str, Any]:
    user = await client.get_entity(entity)
    return {
        "id": user.id,
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "phone": getattr(user, "phone", None),
        "bot": bool(getattr(user, "bot", False)),
        "verified": bool(getattr(user, "verified", False)),
        "premium": bool(getattr(user, "premium", False)),
    }
