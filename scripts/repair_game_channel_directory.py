from __future__ import annotations

import asyncio
import random
import re
import sys
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types
from telethon.errors import FloodWaitError

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database


TARGET_CHANNEL_SETTING = "mission.game_channel_directory.v1.channel_id"
RETRY_DELAY = (1.2, 2.4)
CHUNK_LIMIT = 3500

FAILED_USERNAMES = [
    "merkur_casino_spiele_onlineon", "metagamenews", "minecraftj", "minecrafti",
    "videos_games", "mkgamingconsole", "mobile_gaminguz", "gamingonphone",
    "gaming_mobile22", "monte_dota2", "monte_esports", "cs_2_mrkt", "nemigagg",
    "nintendom", "nintendo_market", "nintendo55", "nintendonewsofficial",
    "thenotgames", "oyun_haberleri", "fnitemshop", "frifasbr", "freew_fire",
    "freefirepanelffhack", "free_pc_games_channel", "gametynews", "game_channel7",
    "warzoneclubnews", "game_news_gm", "news_game", "game_shop_russia",
    "gamef_channel", "gamefi_officialann", "gamesnintendoswitch", "ps2gamesfree",
    "csgoskin77", "gamestarternews", "gaming_news4", "gaming_news_ogc",
    "thegamingnewsdaily", "gaming_news1", "gamingreports", "gaming_news6",
    "gatto_game", "gta6videogame", "wizardsuniteinfode", "hltvtelegram",
    "hobby_games", "horror_mods_new", "valorant_rest", "imshrshop",
    "robloxqueen", "iccup", "game_channel5", "indie_ag", "indiegametv",
    "indie_game0", "indiegam", "x90fpspubgm", "gamingl", "roblox",
    "arigamingstore", "artofvideogames", "karpz_vlr", "atiranconsole",
    "aurora_dota2", "b8esportsgg", "bazimobilechannel", "beastgames2027",
    "bigindiegames", "bmdaccount", "bundesligagermania",
    "console_to_mobile_gaming", "consoler_gaming", "counter_strike_pro",
    "qounter_strike2", "cs2_plus", "cubepass", "cwgames_channel",
    "team_cybershoke", "csru_official", "deutschland_gaming", "diletantgamer",
    "mr_haselixbox", "dota2ti_ru", "esportsx", "gamingc", "eg_proxy",
    "epicore_valorant", "ezsteam_ir", "robloxfluxnews", "pubgk", "fortnite_br",
    "fort_chaleng"
]

PERSIAN_MARKERS = set("پچژگ")
IRANIAN_WORDS = {
    "ایران", "ایرانی", "ایرانیان", "فارسی", "فارس", "تهران", "مشهد",
    "شیراز", "اصفهان", "تبریز", "کرج", "قم", "اهواز", "رشت", "کرمان",
    "persian", "iran", "iranian", "farsi"
}


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_iranian(title: str, username: str, about: str = "") -> bool:
    text = clean_text(f"{title} {username} {about}").casefold()
    if any(word in text for word in IRANIAN_WORDS):
        return True
    if any(word in text for word in (
        "بازی", "گیم", "گیمینگ", "گیمر", "اخبار بازی",
        "بازی موبایل", "بازی کامپیوتری", "کنسول"
    )):
        return True
    return sum(ch in PERSIAN_MARKERS for ch in text) >= 2


COUNT_RE = re.compile(r"^👥 مشترکین: ([0-9,]+|نامشخص)$", re.MULTILINE)
ENTRY_RE = re.compile(
    r"(?ms)^\d+\.\s*(.+?)\n"
    r"👥 مشترکین: ([0-9,]+|نامشخص)\n"
    r"@([A-Za-z0-9_]{4,})\n"
    r"https://t\.me/\3"
)


async def parse_existing_directory(client, channel) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    async for message in client.iter_messages(channel, limit=500):
        text = getattr(message, "message", "") or ""
        for match in ENTRY_RE.finditer(text):
            title = clean_text(match.group(1))
            raw_count = match.group(2)
            username = match.group(3).casefold()
            participants = None if raw_count == "نامشخص" else int(raw_count.replace(",", ""))
            entries[username] = {
                "title": title,
                "username": username,
                "participants": participants,
                "iranian": is_iranian(title, username),
            }
    return entries


async def fetch_one(client, username: str) -> dict:
    attempts = 0
    while True:
        attempts += 1
        try:
            entity = await client.get_entity(username)
            if not isinstance(entity, types.Channel) or not bool(getattr(entity, "broadcast", False)):
                raise ValueError("not_public_broadcast_channel")

            participants = getattr(entity, "participants_count", None)
            about = ""
            if participants is None:
                full = await client(functions.channels.GetFullChannelRequest(channel=entity))
                participants = getattr(full.full_chat, "participants_count", None)
                about = clean_text(getattr(full.full_chat, "about", "") or "")

            title = clean_text(getattr(entity, "title", "") or username)
            return {
                "title": title,
                "username": username.casefold(),
                "participants": int(participants) if isinstance(participants, int) else None,
                "iranian": is_iranian(title, username, about),
            }
        except FloodWaitError as exc:
            wait_seconds = max(1, int(getattr(exc, "seconds", 30))) + 2
            print(
                f"GAME_DIRECTORY_RETRY_FLOOD username=@{username} "
                f"wait={wait_seconds}s attempt={attempts}"
            )
            await asyncio.sleep(wait_seconds)
        except Exception:
            raise


def sort_key(item: dict):
    p = item["participants"]
    return (1 if p is None else 0, -(p or 0), item["title"].casefold(), item["username"])


def fmt_count(value: int | None) -> str:
    return "نامشخص" if value is None else f"{value:,}"


async def send_chunks(client, channel, text: str) -> int:
    blocks: list[str] = []
    current = ""
    for piece in text.split("\n\n"):
        candidate = piece if not current else current + "\n\n" + piece
        if len(candidate) > CHUNK_LIMIT:
            if current:
                blocks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        blocks.append(current)

    for index, chunk in enumerate(blocks, 1):
        await client.send_message(channel, chunk)
        print(f"GAME_DIRECTORY_REPAIR_SEND part={index}/{len(blocks)} chars={len(chunk)}")
        if index != len(blocks):
            await asyncio.sleep(random.uniform(*RETRY_DELAY))
    return len(blocks)


async def clear_channel(client, channel) -> int:
    ids: list[int] = []
    async for message in client.iter_messages(channel, limit=500):
        ids.append(message.id)
    deleted = 0
    for offset in range(0, len(ids), 100):
        batch = ids[offset:offset + 100]
        if batch:
            await client.delete_messages(channel, batch)
            deleted += len(batch)
            await asyncio.sleep(random.uniform(0.5, 1.0))
    print(f"GAME_DIRECTORY_REPAIR_CLEARED={deleted}")
    return deleted


async def main() -> None:
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
            raise RuntimeError("No authorized Telegram user session is available.")

        channel_id_raw = await db.get_setting(TARGET_CHANNEL_SETTING)
        if not channel_id_raw:
            raise RuntimeError("Existing gaming directory channel id is missing.")

        channel = await client.get_entity(int(channel_id_raw))
        print(f"GAME_DIRECTORY_REPAIR_CHANNEL={channel.id}")

        entries = await parse_existing_directory(client, channel)
        print(f"GAME_DIRECTORY_REPAIR_EXISTING={len(entries)}")

        for index, username in enumerate(FAILED_USERNAMES, 1):
            if username in entries:
                continue
            try:
                item = await fetch_one(client, username)
                entries[username] = item
                print(
                    f"GAME_DIRECTORY_REPAIR_DETAIL={index}/{len(FAILED_USERNAMES)} "
                    f"username=@{username} subscribers={item['participants']} "
                    f"iranian={item['iranian']}"
                )
            except Exception as exc:
                print(
                    f"GAME_DIRECTORY_REPAIR_DETAIL_FAILED={index}/{len(FAILED_USERNAMES)} "
                    f"username=@{username} error={type(exc).__name__}"
                )
                continue
            await asyncio.sleep(random.uniform(*RETRY_DELAY))

        expected = 282
        print(f"GAME_DIRECTORY_REPAIR_COLLECTED={len(entries)} expected={expected}")

        if len(entries) < expected:
            raise RuntimeError(
                f"Directory is still incomplete: {len(entries)}/{expected}. "
                "Do not publish a partial rebuild."
            )

        entries_list = sorted(entries.values(), key=sort_key)
        iranian = [x for x in entries_list if x["iranian"]]
        foreign = [x for x in entries_list if not x["iranian"]]

        await clear_channel(client, channel)

        summary = await client.send_message(
            channel,
            "🎮 فهرست کانال‌های گیم\n\n"
            f"کل کانال‌ها: {len(entries_list)}\n"
            f"ایرانی: {len(iranian)}\n"
            f"خارجی: {len(foreign)}\n"
            "مرتب‌سازی هر دسته: تعداد مشترکین از بیشترین به کمترین\n"
            "آمار بر اساس تعداد مشترکین قابل مشاهده توسط Telegram در زمان ثبت است.\n"
            "تشخیص ایرانی/خارجی بر پایه عنوان و نام کاربری و نشانه‌های زبانی انجام شده و برای موارد مرزی قطعی نیست."
        )
        with suppress(Exception):
            await client.pin_message(channel, summary, notify=False)
        await asyncio.sleep(random.uniform(*RETRY_DELAY))

        for label, emoji, items in (
            ("کانال‌های ایرانی", "🇮🇷", iranian),
            ("کانال‌های خارجی", "🌍", foreign),
        ):
            blocks = [
                f"{emoji} {label}\nتعداد: {len(items)}\n"
                "مرتب‌سازی: مشترکین بیشتر ← پایین‌تر\n"
            ]
            for number, item in enumerate(items, 1):
                blocks.append(
                    f"{number}. {item['title']}\n"
                    f"👥 مشترکین: {fmt_count(item['participants'])}\n"
                    f"@{item['username']}\n"
                    f"https://t.me/{item['username']}"
                )
            await send_chunks(client, channel, "\n\n".join(blocks))
            await asyncio.sleep(random.uniform(*RETRY_DELAY))

        await db.set_setting("mission.game_channel_directory.v2.done", "1")
        await db.set_setting("mission.game_channel_directory.v2.total", str(len(entries_list)))
        await db.set_setting("mission.game_channel_directory.v2.iranian", str(len(iranian)))
        await db.set_setting("mission.game_channel_directory.v2.foreign", str(len(foreign)))

        print(
            "GAME_DIRECTORY_REPAIR_DONE "
            f"channel={channel.id} total={len(entries_list)} "
            f"iranian={len(iranian)} foreign={len(foreign)}"
        )
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
