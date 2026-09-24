from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database


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

        done = await db.get_setting("mission.account_cleanup.v2.done")
        moved = int(await db.get_setting("mission.account_cleanup.v2.archived", "0"))

        filters_result = await client(functions.messages.GetDialogFiltersRequest())
        filters = list(getattr(filters_result, "filters", filters_result) or [])
        custom = [f for f in filters if isinstance(f, types.DialogFilter)]
        titles = {f.title for f in custom}

        archived = await client.get_dialogs(folder=1)
        active = await client.get_dialogs(folder=0)

        # Recompute conservative stale candidates after cleanup. There should
        # be no old unread-free channels/bots left that match the same rules.
        now = datetime.now(timezone.utc)
        channel_cutoff = now - timedelta(days=30)
        bot_cutoff = now - timedelta(days=30)
        stale_channels = 0
        stale_bots = 0

        for dialog in active:
            entity = dialog.entity
            if getattr(dialog, "pinned", False) or int(getattr(dialog, "unread_count", 0) or 0) > 0:
                continue
            message = getattr(dialog, "message", None)
            dt = getattr(message, "date", None) if message else None
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if isinstance(entity, types.Channel) and getattr(entity, "broadcast", False):
                if dt and dt < channel_cutoff:
                    stale_channels += 1
            elif isinstance(entity, types.User) and getattr(entity, "bot", False):
                if dt and dt < bot_cutoff:
                    stale_bots += 1

        duplicate_titles = {"👥 گروه‌ها", "🤖 ربات‌ها", "👤 شخصی"}

        result = {
            "done": done,
            "moved": moved,
            "active": len(active),
            "archived": len(archived),
            "custom_folders": [(f.id, f.title) for f in custom],
            "gaming_folder_present": "🌍 گیم خارجی" in titles,
            "duplicate_folders_present": sorted(titles & duplicate_titles),
            "stale_active_channels": stale_channels,
            "stale_active_bots": stale_bots,
        }
        print("ACCOUNT_CLEANUP_V2_VERIFY=" + repr(result))

        if done != "1":
            raise RuntimeError("cleanup mission not marked complete")
        if "🌍 گیم خارجی" not in titles:
            raise RuntimeError("gaming folder missing")
        if titles & duplicate_titles:
            raise RuntimeError("duplicate folders still exist")
        if stale_channels or stale_bots:
            raise RuntimeError("stale cleanup candidates still remain in active folder")

        print("ACCOUNT_CLEANUP_V2_VERIFY_OK")
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
