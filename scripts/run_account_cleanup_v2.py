from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import suppress

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database


DONE = "mission.account_cleanup.v2.done"
DIRECTORY_SETTING = "mission.game_channel_directory.v1.channel_id"

OUR_DUPLICATE_TITLES = {
    "👥 گروه‌ها",
    "🤖 ربات‌ها",
    "👤 شخصی",
}

GAMING_FOREIGN_TITLE = "🌍 گیم خارجی"
GAMING_IRAN_TITLE = "🎮 گیم ایران"

ENTRY_RE = __import__("re").compile(
    r"(?ms)^\d+\.\s*(.+?)\n👥 مشترکین: [^\n]+\n@([A-Za-z0-9_]{4,})\nhttps://t\.me/\2"
)

CHANNEL_STALE_DAYS = 30
BOT_STALE_DAYS = 30


async def gaming_usernames(client, db):
    raw = await db.get_setting(DIRECTORY_SETTING)
    if not raw:
        return set(), set()
    channel = await client.get_entity(int(raw))
    iranian, foreign = set(), set()
    current = None
    messages = []
    async for message in client.iter_messages(channel, limit=300):
        messages.append(getattr(message, "message", "") or "")
    for text in reversed(messages):
        if "🇮🇷 کانال‌های ایرانی" in text:
            current = "iranian"
        elif "🌍 کانال‌های خارجی" in text:
            current = "foreign"
        if current:
            for match in ENTRY_RE.finditer(text):
                (iranian if current == "iranian" else foreign).add(match.group(2).casefold())
    return iranian, foreign


def last_date(dialog):
    msg = getattr(dialog, "message", None)
    return getattr(msg, "date", None) if msg else None


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

        filters_result = await client(functions.messages.GetDialogFiltersRequest())
        filters = list(getattr(filters_result, "filters", filters_result) or [])
        custom = {f.id: f for f in filters if isinstance(f, types.DialogFilter)}

        # Remove only the three duplicate folders created by the previous
        # cleanup attempt. Existing user folders remain untouched.
        removed = 0
        for folder_id, f in list(custom.items()):
            if f.title in OUR_DUPLICATE_TITLES:
                await client(functions.messages.UpdateDialogFilterRequest(
                    id=folder_id,
                    filter=None,
                ))
                removed += 1
                print(f"ACCOUNT_CLEANUP_V2_REMOVED_FOLDER id={folder_id} title={f.title}")

        iranian, foreign = await gaming_usernames(client, db)
        gaming = iranian | foreign

        dialogs = await client.get_dialogs(limit=None)
        now = datetime.now(timezone.utc)
        channel_cutoff = now - timedelta(days=CHANNEL_STALE_DAYS)
        bot_cutoff = now - timedelta(days=BOT_STALE_DAYS)

        gaming_dialogs = []
        stale_channels = []
        stale_bots = []

        for dialog in dialogs:
            entity = dialog.entity
            username = (getattr(entity, "username", None) or "").casefold()
            pinned = bool(getattr(dialog, "pinned", False))
            unread = int(getattr(dialog, "unread_count", 0) or 0)
            dt = last_date(dialog)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if isinstance(entity, types.Channel) and bool(getattr(entity, "broadcast", False)):
                if username in gaming:
                    if not pinned and unread == 0:
                        gaming_dialogs.append(dialog)
                    continue

                if (
                    not pinned
                    and unread == 0
                    and dt is not None
                    and dt < channel_cutoff
                ):
                    stale_channels.append(dialog)

            elif isinstance(entity, types.User) and bool(getattr(entity, "bot", False)):
                if (
                    not pinned
                    and unread == 0
                    and dt is not None
                    and dt < bot_cutoff
                ):
                    stale_bots.append(dialog)

        print(
            "ACCOUNT_CLEANUP_V2_COUNTS "
            f"dialogs={len(dialogs)} "
            f"gaming={len(gaming_dialogs)} "
            f"stale_channels={len(stale_channels)} "
            f"stale_bots={len(stale_bots)} "
            f"already_archived={sum(1 for d in dialogs if getattr(d, 'folder_id', None) == 1)}"
        )

        to_archive = gaming_dialogs + stale_channels + stale_bots
        archived = 0
        for start in range(0, len(to_archive), 50):
            batch = to_archive[start:start + 50]
            if not batch:
                continue
            await client.edit_folder(batch, 1)
            archived += len(batch)
            print(
                f"ACCOUNT_CLEANUP_V2_ARCHIVED batch={start // 50 + 1} "
                f"count={len(batch)} total={archived}"
            )
            await asyncio.sleep(0.7)

        # Make sure the gaming folder that already exists contains all
        # currently-open gaming dialogs, without consuming another folder ID.
        current_filters_result = await client(functions.messages.GetDialogFiltersRequest())
        current_filters = list(getattr(current_filters_result, "filters", current_filters_result) or [])
        by_title = {f.title: f for f in current_filters if isinstance(f, types.DialogFilter)}

        current_dialogs = await client.get_dialogs(limit=None)
        gaming_now = []
        for dialog in current_dialogs:
            entity = dialog.entity
            username = (getattr(entity, "username", None) or "").casefold()
            if isinstance(entity, types.Channel) and getattr(entity, "broadcast", False) and username in gaming:
                value = getattr(dialog, "input_entity", None) or entity
                gaming_now.append(value)

        existing_gaming = by_title.get(GAMING_FOREIGN_TITLE)
        if gaming_now and existing_gaming:
            # The account currently has only foreign gaming dialogs open.
            await client(functions.messages.UpdateDialogFilterRequest(
                id=existing_gaming.id,
                filter=types.DialogFilter(
                    id=existing_gaming.id,
                    title=GAMING_FOREIGN_TITLE,
                    emoticon="🌍",
                    pinned_peers=[],
                    include_peers=gaming_now,
                    exclude_peers=[],
                    exclude_archived=False,
                ),
            ))
            print(
                f"ACCOUNT_CLEANUP_V2_GAMING_FOLDER id={existing_gaming.id} count={len(gaming_now)}"
            )

        await db.set_setting(DONE, "1")
        await db.set_setting("mission.account_cleanup.v2.archived", str(archived))
        await db.set_setting("mission.account_cleanup.v2.stale_channels", str(len(stale_channels)))
        await db.set_setting("mission.account_cleanup.v2.stale_bots", str(len(stale_bots)))

        print(
            "ACCOUNT_CLEANUP_V2_DONE "
            f"removed_duplicate_folders={removed} archived={archived} "
            f"gaming={len(gaming_dialogs)} stale_channels={len(stale_channels)} "
            f"stale_bots={len(stale_bots)}"
        )
    finally:
        with suppress(Exception):
            await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
