from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from contextlib import suppress

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database

DIRECTORY_SETTING = "mission.game_channel_directory.v1.channel_id"
DONE_SETTING = "mission.account_cleanup.v1.done"

TITLE_GAMING_IR = "🎮 گیم ایران"
TITLE_GAMING_FOREIGN = "🌍 گیم خارجی"
TITLE_GROUPS = "👥 گروه‌ها"
TITLE_BOTS = "🤖 ربات‌ها"
TITLE_PERSONAL = "👤 شخصی"
TITLE_CHANNELS = "📺 کانال‌ها"

ENTRY_RE = re.compile(
    r"(?ms)^\d+\.\s*(.+?)\n"
    r"👥 مشترکین: [^\n]+\n"
    r"@([A-Za-z0-9_]{4,})\n"
    r"https://t\.me/\2"
)


async def get_directory_peers(client, db):
    raw = await db.get_setting(DIRECTORY_SETTING)
    if not raw:
        return set(), set()

    channel = await client.get_entity(int(raw))
    iranian: set[str] = set()
    foreign: set[str] = set()
    current = None

    messages = []
    async for message in client.iter_messages(channel, limit=300):
        text = getattr(message, "message", "") or ""
        messages.append(text)

    for text in reversed(messages):
        if "🇮🇷 کانال‌های ایرانی" in text:
            current = "iranian"
        elif "🌍 کانال‌های خارجی" in text:
            current = "foreign"

        if current:
            for match in ENTRY_RE.finditer(text):
                username = match.group(2).casefold()
                if current == "iranian":
                    iranian.add(username)
                else:
                    foreign.add(username)

    return iranian, foreign


def input_peer(dialog):
    value = getattr(dialog, "input_entity", None)
    if value is not None:
        return value
    return dialog.entity


async def main():
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    manager = AccountManager(
        settings.api_id,
        settings.api_hash,
        settings.session_directory,
        db,
    )

    try:
        await manager.connect_saved_sessions()
        client = manager.active() or next(iter(manager.clients.values()), None)
        if not client:
            raise RuntimeError("No authorized Telegram account available.")

        if await db.get_setting(DONE_SETTING):
            print("ACCOUNT_CLEANUP_ALREADY_DONE")
            return

        dialogs = await client.get_dialogs(limit=None)
        print(f"ACCOUNT_CLEANUP_DIALOGS={len(dialogs)}")

        gaming_iran_usernames, gaming_foreign_usernames = await get_directory_peers(client, db)
        gaming_usernames = gaming_iran_usernames | gaming_foreign_usernames
        print(
            f"ACCOUNT_CLEANUP_GAMING_LIST iranian={len(gaming_iran_usernames)} "
            f"foreign={len(gaming_foreign_usernames)} total={len(gaming_usernames)}"
        )

        gaming_iran = []
        gaming_foreign = []
        groups = []
        bots = []
        personal = []
        other_channels = []

        username_by_dialog = {}
        for dialog in dialogs:
            entity = dialog.entity
            username = (getattr(entity, "username", None) or "").casefold()
            username_by_dialog[id(dialog)] = username

            if isinstance(entity, types.User):
                if getattr(entity, "bot", False):
                    bots.append(dialog)
                elif not getattr(entity, "is_self", False):
                    personal.append(dialog)
                continue

            if isinstance(entity, types.Channel):
                if getattr(entity, "megagroup", False):
                    groups.append(dialog)
                elif getattr(entity, "broadcast", False):
                    if username in gaming_iran_usernames:
                        gaming_iran.append(dialog)
                    elif username in gaming_foreign_usernames:
                        gaming_foreign.append(dialog)
                    else:
                        other_channels.append(dialog)
                continue

            if isinstance(entity, types.Chat):
                groups.append(dialog)

        print(
            "ACCOUNT_CLEANUP_COUNTS "
            f"gaming_iran={len(gaming_iran)} "
            f"gaming_foreign={len(gaming_foreign)} "
            f"groups={len(groups)} bots={len(bots)} "
            f"personal={len(personal)} other_channels={len(other_channels)}"
        )

        filters_result = await client(functions.messages.GetDialogFiltersRequest())
        existing = {
            f.title: f
            for f in getattr(filters_result, "filters", [])
            if isinstance(f, types.DialogFilter)
        }
        used_ids = {
            f.id
            for f in getattr(filters_result, "filters", [])
            if isinstance(f, types.DialogFilter)
        }

        desired = []
        if gaming_iran:
            desired.append((TITLE_GAMING_IR, "🎮", [input_peer(d) for d in gaming_iran]))
        if gaming_foreign:
            desired.append((TITLE_GAMING_FOREIGN, "🌍", [input_peer(d) for d in gaming_foreign]))
        if groups:
            desired.append((TITLE_GROUPS, "👥", []))
        if bots:
            desired.append((TITLE_BOTS, "🤖", []))
        if personal:
            desired.append((TITLE_PERSONAL, "👤", [input_peer(d) for d in personal]))
        if other_channels:
            desired.append((TITLE_CHANNELS, "📺", [input_peer(d) for d in other_channels]))

        next_ids = [i for i in range(2, 11) if i not in used_ids]

        folder_ids = []
        for title, emoticon, include_peers in desired:
            existing_filter = existing.get(title)
            if existing_filter:
                folder_id = existing_filter.id
            else:
                if not next_ids:
                    raise RuntimeError("No free Telegram folder id available.")
                folder_id = next_ids.pop(0)

            folder_ids.append(folder_id)

            if title == TITLE_GROUPS:
                include_peers = []
                filter_obj = types.DialogFilter(
                    id=folder_id,
                    title=title,
                    emoticon=emoticon,
                    groups=True,
                    exclude_archived=True,
                    pinned_peers=[],
                    include_peers=[],
                    exclude_peers=[],
                )
            elif title == TITLE_BOTS:
                filter_obj = types.DialogFilter(
                    id=folder_id,
                    title=title,
                    emoticon=emoticon,
                    bots=True,
                    exclude_archived=True,
                    pinned_peers=[],
                    include_peers=[],
                    exclude_peers=[],
                )
            else:
                filter_obj = types.DialogFilter(
                    id=folder_id,
                    title=title,
                    emoticon=emoticon,
                    pinned_peers=[],
                    include_peers=include_peers,
                    exclude_peers=[],
                    exclude_archived=False,
                )

            await client(functions.messages.UpdateDialogFilterRequest(
                id=folder_id,
                filter=filter_obj,
            ))
            print(f"ACCOUNT_CLEANUP_FOLDER id={folder_id} title={title} count={len(include_peers)}")

        if folder_ids:
            # Put the new organization folders first, then keep other custom
            # folders in their existing order.
            old_order = [
                f.id for f in getattr(filters_result, "filters", [])
                if isinstance(f, types.DialogFilter) and f.id not in folder_ids
            ]
            await client(functions.messages.UpdateDialogFiltersOrderRequest(
                order=folder_ids + old_order
            ))

        # Archive only gaming channels which are not pinned and have no unread
        # messages. This reduces noise without touching active conversations.
        to_archive = [
            d for d in gaming_iran + gaming_foreign
            if not getattr(d, "pinned", False) and getattr(d, "unread_count", 0) == 0
        ]
        print(f"ACCOUNT_CLEANUP_ARCHIVE_ELIGIBLE={len(to_archive)}")

        archived = 0
        for start in range(0, len(to_archive), 50):
            batch = to_archive[start:start + 50]
            if not batch:
                continue
            try:
                await client.edit_folder(batch, 1)
                archived += len(batch)
            except Exception as exc:
                print(
                    f"ACCOUNT_CLEANUP_ARCHIVE_BATCH_FAILED start={start} "
                    f"error={type(exc).__name__}"
                )
            await asyncio.sleep(0.7)

        # Validate the archive count and folder definitions after the changes.
        final_filters = await client(functions.messages.GetDialogFiltersRequest())
        final_titles = {
            f.title: f.id
            for f in getattr(final_filters, "filters", [])
            if isinstance(f, types.DialogFilter)
        }

        if not all(title in final_titles for title, _, _ in desired):
            raise RuntimeError("One or more organization folders were not persisted.")

        await db.set_setting(DONE_SETTING, "1")
        await db.set_setting("mission.account_cleanup.v1.dialogs", str(len(dialogs)))
        await db.set_setting("mission.account_cleanup.v1.archived_gaming", str(archived))

        print(
            "ACCOUNT_CLEANUP_DONE "
            f"dialogs={len(dialogs)} "
            f"folders={len(desired)} "
            f"gaming_iran={len(gaming_iran)} "
            f"gaming_foreign={len(gaming_foreign)} "
            f"archived_gaming={archived}"
        )
    finally:
        with suppress(Exception):
            await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
