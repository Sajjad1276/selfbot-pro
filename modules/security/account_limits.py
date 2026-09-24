from __future__ import annotations

from typing import Any


async def get_account_config(client: Any) -> dict[str, object]:
    try:
        result = await client.get_me()
        return {
            "id": result.id,
            "restricted": bool(getattr(result, "restricted", False)),
            "restriction_reason": getattr(result, "restriction_reason", None),
        }
    except Exception as exc:
        return {"error": str(exc)}
