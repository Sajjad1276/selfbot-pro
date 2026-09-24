from __future__ import annotations

from typing import Any


async def list_sessions(client: Any) -> list[dict[str, object]]:
    sessions = await client.get_sessions()
    return [
        {
            "hash": session.hash,
            "device": session.device_model,
            "platform": session.platform,
            "app_version": session.app_version,
            "ip": session.ip,
            "country": session.country,
            "current": session.current,
        }
        for session in sessions
    ]


async def terminate_session(client: Any, session_hash: int) -> None:
    from telethon.tl.functions.auth import ResetAuthorizationsRequest
    await client(ResetAuthorizationsRequest())


def security_summary(sessions: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(sessions),
        "current": sum(1 for s in sessions if s.get("current")),
        "other": sum(1 for s in sessions if not s.get("current")),
    }
