from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database

ENTRY_RE = re.compile(r"(?ms)^\d+\.\s*(.+?)\n👥 مشترکین: [^\n]+\n@([A-Za-z0-9_]{4,})\nhttps://t\.me/\2")


async def main():
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    manager = AccountManager(settings.api_id, settings.api_hash, settings.session_directory, db)

    try:
        await manager.connect_saved_sessions()
        client = manager.active() or next(iter(manager.clients.values()), None)
        if not client:
            raise RuntimeError("No authorized account")

        done = await db.get_setting("mission.account_cleanup.v1.done")
        archived_target = int(await db.get_setting("mission.account_cleanup.v1.archived_gaming", "0"))

        directory_id = await db.get_setting("mission.game_channel_directory.v1.channel_id")
        directory = await client.get_entity(int(directory_id))

        gaming: set[str] = set()
        async for msg in client.iter_messages(directory, limit=300):
            text = getattr(msg, "message", "") or ""
            for m in ENTRY_RE.finditer(text):
                gaming.add(m.group(2).casefold())

        archived = await client.get_dialogs(folder=1)
        active = await client.get_dialogs(folder=0)

        archived_gaming = 0
        active_gaming = 0
        for d in archived:
            u = (getattr(d.entity, "username", None) or "").casefold()
            if u in gaming:
                archived_gaming += 1
        for d in active:
            u = (getattr(d.entity, "username", None) or "").casefold()
            if u in gaming:
                active_gaming += 1

        raw_filters = await client(functions.messages.GetDialogFiltersRequest())
        filters = getattr(raw_filters, "filters", raw_filters)
        folder_info = []
        for f in filters or []:
            if isinstance(f, types.DialogFilter):
                folder_info.append((f.id, f.title))

        expected_titles = {
            "🎮 گیم ایران",
            "🌍 گیم خارجی",
            "👥 گروه‌ها",
            "🤖 ربات‌ها",
            "👤 شخصی",
            "📺 کانال‌ها",
        }
        actual_titles = {title for _, title in folder_info}
        missing = sorted(expected_titles - actual_titles)

        result = {
            "done": done,
            "archived_target": archived_target,
            "gaming_list": len(gaming),
            "active_dialogs": len(active),
            "archived_dialogs": len(archived),
            "archived_gaming": archived_gaming,
            "active_gaming": active_gaming,
            "folders": folder_info,
            "missing_folders": missing,
        }
        print("ACCOUNT_CLEANUP_VERIFY=" + repr(result))

        if done != "1":
            raise RuntimeError("cleanup setting is not marked done")
        if not expected_titles.issubset(actual_titles):
            raise RuntimeError("one or more requested folders are missing")
        if archived_gaming < min(archived_target, len(gaming)) - 1:
            raise RuntimeError("gaming archive count is lower than recorded target")

        print("ACCOUNT_CLEANUP_VERIFY_OK")
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
