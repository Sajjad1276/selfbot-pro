from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.accounts.manager import AccountManager
from modules.utils.database import Database
from config import get_settings

ENTRY_RE = re.compile(
    r"(?ms)^\d+\.\s*(.+?)\n"
    r"👥 مشترکین: ([0-9,]+|نامشخص)\n"
    r"@([A-Za-z0-9_]{4,})\n"
    r"https://t\.me/\3"
)


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    manager = AccountManager(settings.api_id, settings.api_hash, settings.session_directory, db)
    try:
        await manager.connect_saved_sessions()
        client = manager.active() or next(iter(manager.clients.values()), None)
        if not client:
            raise RuntimeError("No authorized Telegram user session")

        channel_id = int(await db.get_setting("mission.game_channel_directory.v1.channel_id"))
        channel = await client.get_entity(channel_id)

        entries = []
        section = None
        messages = []
        async for message in client.iter_messages(channel, limit=200):
            text = getattr(message, "message", "") or ""
            messages.append(text)
        for text in reversed(messages):
            if "🇮🇷 کانال‌های ایرانی" in text:
                section = "iranian"
            if "🌍 کانال‌های خارجی" in text:
                section = "foreign"
            for m in ENTRY_RE.finditer(text):
                if section not in {"iranian", "foreign"}:
                    continue
                count = None if m.group(2) == "نامشخص" else int(m.group(2).replace(",", ""))
                entries.append(
                    {
                        "title": m.group(1).strip(),
                        "username": m.group(3).casefold(),
                        "count": count,
                        "section": section,
                    }
                )

        unique = {e["username"] for e in entries}
        iranian = [e for e in entries if e["section"] == "iranian"]
        foreign = [e for e in entries if e["section"] == "foreign"]

        def sorted_ok(items):
            counts = [e["count"] for e in items if e["count"] is not None]
            return all(a >= b for a, b in zip(counts, counts[1:]))

        checks = {
            "total": len(entries),
            "unique": len(unique),
            "iranian": len(iranian),
            "foreign": len(foreign),
            "sorted_iranian": sorted_ok(iranian),
            "sorted_foreign": sorted_ok(foreign),
            "channel_id": channel.id,
        }
        if not (
            checks["total"] == 282
            and checks["unique"] == 282
            and checks["iranian"] == 48
            and checks["foreign"] == 234
            and checks["sorted_iranian"]
            and checks["sorted_foreign"]
        ):
            raise RuntimeError(f"Directory verification failed: {checks}")

        print(
            "GAME_DIRECTORY_VERIFY_OK "
            f"channel={channel.id} total={checks['total']} "
            f"iranian={checks['iranian']} foreign={checks['foreign']} "
            f"sorted_iranian={checks['sorted_iranian']} "
            f"sorted_foreign={checks['sorted_foreign']}"
        )
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
