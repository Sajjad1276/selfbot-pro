from __future__ import annotations

from typing import Any


async def resolve_id(client: Any, value: str | int) -> dict[str, Any]:
    entity = await client.get_entity(int(value) if str(value).lstrip("-").isdigit() else value)
    return {
        "id": entity.id,
        "username": getattr(entity, "username", None),
        "name": " ".join(x for x in [getattr(entity, "first_name", None), getattr(entity, "last_name", None)] if x)
        or getattr(entity, "title", None),
        "type": entity.__class__.__name__,
    }
