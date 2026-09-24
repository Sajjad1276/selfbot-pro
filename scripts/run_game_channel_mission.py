from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from telethon import TelegramClient, functions, types

from config import get_settings
from modules.utils.database import Database
from modules.accounts.manager import AccountManager


SEARCHES = [
    "game", "gaming", "games", "videogame", "video games", "esports",
    "gaming news", "game news", "game channel", "indie game", "indie games",
    "pc gaming", "mobile gaming", "console gaming", "playstation", "xbox",
    "nintendo", "steam", "minecraft", "roblox", "fortnite", "pubg", "free fire",
    "valorant", "cs2", "counter strike", "dota", "league of legends",
    " بازی", "گیم", "گیمینگ", "اخبار بازی", "بازی موبایل", "بازی کامپیوتری",
    "پلی استیشن", "ایکس باکس", "نینتندو", "استیم",
    "spiele", "gaming deutsch", "spiele news",
    "ألعاب", "ألعاب فيديو", "أخبار الألعاب",
    "игры", "гейминг", "игровые новости",
    "oyun", "oyun haberleri",
]

PAGE_LIMIT = 100
SEARCH_DELAY = (1.0, 2.0)
SAVE_DELAY = (0.8, 1.6)
CHUNK_LIMIT = 3600


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    done_key = "mission.game_channels.v1.done"
    if await db.get_setting(done_key):
        print("GAME_CHANNEL_MISSION_ALREADY_DONE")
        await db.close()
        return

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
            raise RuntimeError("No authorized Telegram user session is available.")

        me = await client.get_me()
        print(f"GAME_CHANNEL_MISSION_ACCOUNT={me.id}")

        found: dict[str, dict[str, str]] = {}
        completed_queries = 0

        for query in SEARCHES:
            try:
                result = await client(functions.contacts.SearchRequest(q=query, limit=PAGE_LIMIT))
            except Exception as exc:
                print(f"SEARCH_FAILED query={query!r} error={type(exc).__name__}")
                await asyncio.sleep(random.uniform(*SEARCH_DELAY))
                continue

            for entity in getattr(result, "chats", []) or []:
                if not isinstance(entity, types.Channel):
                    continue
                if not bool(getattr(entity, "broadcast", False)):
                    continue
                username = (getattr(entity, "username", None) or "").strip().lower()
                title = (getattr(entity, "title", None) or "").strip()
                if not username or not title:
                    continue

                key = username
                found.setdefault(
                    key,
                    {
                        "title": title,
                        "username": username,
                        "query": query,
                    },
                )

            completed_queries += 1
            print(
                f"GAME_CHANNEL_MISSION_QUERY={completed_queries}/{len(SEARCHES)} "
                f"unique={len(found)} query={query!r}"
            )
            await asyncio.sleep(random.uniform(*SEARCH_DELAY))

        items = sorted(
            found.values(),
            key=lambda x: (x["title"].casefold(), x["username"]),
        )

        header = (
            "🎮 مأموریت پیدا کردن کانال‌های گیم\n\n"
            f"زمان اجرا: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"تعداد جست‌وجوها: {completed_queries}/{len(SEARCHES)}\n"
            f"تعداد کانال‌های عمومی یکتا: {len(items)}\n\n"
            "فقط کانال‌های عمومی که Telegram در نتایج جست‌وجوی عمومی برگردانده ذخیره شده‌اند.\n"
        )

        if not items:
            await client.send_message("me", header + "\nنتیجه‌ای پیدا نشد.")
        else:
            chunks: list[str] = [header]
            current = header
            part = 0

            for index, item in enumerate(items, 1):
                line = (
                    f"{index}. {item['title']}\n"
                    f"@{item['username']}\n"
                    f"https://t.me/{item['username']}\n"
                    f"کلید پیدا شدن: {item['query']}\n\n"
                )
                if len(current) + len(line) > CHUNK_LIMIT:
                    chunks.append(current)
                    current = line
                else:
                    current += line
            if current.strip():
                chunks.append(current)

            for part, text in enumerate(chunks, 1):
                prefix = f"بخش {part}/{len(chunks)}\n" if len(chunks) > 1 else ""
                await client.send_message("me", prefix + text)
                await asyncio.sleep(random.uniform(*SAVE_DELAY))

        await db.set_setting(done_key, "1")
        await db.set_setting("mission.game_channels.v1.count", str(len(items)))
        await db.set_setting("mission.game_channels.v1.queries", str(completed_queries))
        print(f"GAME_CHANNEL_MISSION_DONE channels={len(items)} queries={completed_queries}")
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
