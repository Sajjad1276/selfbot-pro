from __future__ import annotations

import asyncio
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from contextlib import suppress

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types

from config import get_settings
from modules.utils.database import Database
from modules.accounts.manager import AccountManager


CHUNK_LIMIT = 3500
DETAIL_DELAY = (0.20, 0.55)
SEND_DELAY = (0.75, 1.35)

HEADER_MARKER = "🎮 مأموریت پیدا کردن کانال‌های گیم"
LINK_RE = re.compile(r"https://t\.me/([A-Za-z0-9_]{4,})")
PERSIAN_MARKERS = set("پچژگ")
IRANIAN_WORDS = {
    "ایران", "ایرانی", "ایرانیان", "فارسی", "فارس", "تهران", "مشهد",
    "شیراز", "اصفهان", "تبریز", "کرج", "قم", "اهواز", "رشت", "کرمان",
    "persian", "iran", "iranian", "farsi"
}


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_iranian(title: str, username: str, about: str) -> bool:
    text = clean_text(f"{title} {username} {about}").casefold()
    if any(word in text for word in IRANIAN_WORDS):
        return True

    # Farsi-specific letters are a strong signal that the channel is aimed
    # at Persian/Iranian readers, especially together with gaming terms.
    marker_hits = sum(ch in PERSIAN_MARKERS for ch in text)
    farsi_words = any(
        word in text
        for word in (
            "بازی", "گیم", "گیمینگ", "گیمر", "اخبار بازی",
            "بازی موبایل", "بازی کامپیوتری", "کنسول"
        )
    )
    return farsi_words or marker_hits >= 2


async def collect_saved_usernames(client) -> list[str]:
    usernames: list[str] = []
    seen: set[str] = set()
    messages = []

    async for message in client.iter_messages("me", limit=500):
        text = getattr(message, "message", "") or ""
        if not isinstance(text, str):
            continue
        if HEADER_MARKER in text or "کلید پیدا شدن:" in text:
            messages.append(text)

    for text in messages:
        for username in LINK_RE.findall(text):
            key = username.casefold()
            if key not in seen:
                seen.add(key)
                usernames.append(key)

    return usernames


async def fetch_channel_info(client, username: str) -> dict:
    entity = await client.get_entity(username)
    if not isinstance(entity, types.Channel) or not bool(getattr(entity, "broadcast", False)):
        raise ValueError("not_public_broadcast_channel")

    full = await client(functions.channels.GetFullChannelRequest(channel=entity))
    full_chat = full.full_chat
    about = clean_text(getattr(full_chat, "about", "") or "")
    participants = getattr(full_chat, "participants_count", None)
    if participants is None:
        participants = getattr(entity, "participants_count", None)

    return {
        "title": clean_text(getattr(entity, "title", "") or username),
        "username": username,
        "participants": int(participants) if isinstance(participants, int) else None,
        "about": about[:700],
        "iranian": is_iranian(
            clean_text(getattr(entity, "title", "")),
            username,
            about,
        ),
    }


def fmt_count(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    return f"{value:,}"


def sort_key(item: dict):
    participants = item["participants"]
    return (
        1 if participants is None else 0,
        -(participants or 0),
        item["title"].casefold(),
        item["username"],
    )


async def send_chunks(client, peer, text: str, delay: tuple[float, float] = SEND_DELAY) -> int:
    chunks: list[str] = []
    current = ""

    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) > CHUNK_LIMIT:
            if current:
                chunks.append(current)
            current = block
        else:
            current = candidate

    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks, 1):
        await client.send_message(peer, chunk)
        print(f"GAME_DIRECTORY_SEND part={index}/{len(chunks)} chars={len(chunk)}")
        if index != len(chunks):
            await asyncio.sleep(random.uniform(*delay))

    return len(chunks)


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()

    done_key = "mission.game_channel_directory.v1.done"
    if await db.get_setting(done_key):
        print("GAME_DIRECTORY_MISSION_ALREADY_DONE")
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
        print(f"GAME_DIRECTORY_ACCOUNT={me.id}")

        usernames = await collect_saved_usernames(client)
        print(f"GAME_DIRECTORY_SAVED_CHANNELS={len(usernames)}")

        if not usernames:
            raise RuntimeError("No gaming channel list was found in Saved Messages.")

        found: list[dict] = []
        failed: list[str] = []

        for index, username in enumerate(usernames, 1):
            try:
                item = await fetch_channel_info(client, username)
                found.append(item)
                print(
                    f"GAME_DIRECTORY_DETAIL={index}/{len(usernames)} "
                    f"username=@{username} subscribers={item['participants']} "
                    f"iranian={item['iranian']}"
                )
            except Exception as exc:
                failed.append(username)
                print(
                    f"GAME_DIRECTORY_DETAIL_FAILED={index}/{len(usernames)} "
                    f"username=@{username} error={type(exc).__name__}"
                )
            await asyncio.sleep(random.uniform(*DETAIL_DELAY))

        if not found:
            raise RuntimeError("Channel metadata collection returned no usable channels.")

        iranian = sorted((x for x in found if x["iranian"]), key=sort_key)
        foreign = sorted((x for x in found if not x["iranian"]), key=sort_key)

        title = "فهرست کانال‌های گیم | مرتب‌شده بر اساس آمار"
        about = (
            "فهرست کانال‌های گیم که از جست‌وجوی عمومی Telegram جمع‌آوری شده‌اند. "
            "دسته‌بندی ایرانی/خارجی بر اساس نشانه‌های زبانی و محتوای قابل مشاهده انجام شده است."
        )

        created = await client(
            functions.channels.CreateChannelRequest(
                title=title,
                about=about,
                broadcast=True,
                megagroup=False,
            )
        )
        channel = created.chats[0]
        print(f"GAME_DIRECTORY_CHANNEL_CREATED={channel.id}")

        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        summary = (
            "🎮 فهرست کانال‌های گیم\n\n"
            f"زمان ساخت: {created_at}\n"
            f"کل کانال‌های قابل پردازش: {len(usernames)}\n"
            f"کانال‌های پردازش‌شده: {len(found)}\n"
            f"ایرانی: {len(iranian)}\n"
            f"خارجی: {len(foreign)}\n"
            f"بدون آمار قابل دریافت: "
            f"{sum(1 for x in found if x['participants'] is None)}\n"
            f"ناموفق در دریافت جزئیات: {len(failed)}\n\n"
            "مرتب‌سازی هر دسته بر اساس تعداد مشترکین، از بیشترین به کمترین است.\n"
            "دسته‌بندی ایرانی/خارجی از روی عنوان، نام کاربری و توضیحات قابل مشاهده انجام شده و ممکن است برای بعضی کانال‌ها قطعی نباشد."
        )
        summary_message = await client.send_message(channel, summary)
        with suppress(Exception):
            await client.pin_message(channel, summary_message, notify=False)
        await asyncio.sleep(random.uniform(*SEND_DELAY))

        for label, emoji, items in (
            ("کانال‌های ایرانی", "🇮🇷", iranian),
            ("کانال‌های خارجی", "🌍", foreign),
        ):
            section_header = (
                f"{emoji} {label}\n"
                f"تعداد: {len(items)}\n"
                "مرتب‌سازی: تعداد مشترکین از بیشترین به کمترین\n\n"
            )
            blocks = [section_header]

            for number, item in enumerate(items, 1):
                block = (
                    f"{number}. {item['title']}\n"
                    f"👥 مشترکین: {fmt_count(item['participants'])}\n"
                    f"@{item['username']}\n"
                    f"https://t.me/{item['username']}\n"
                )
                if item["about"]:
                    block += f"📝 {item['about'][:280]}\n"

                if sum(len(x) for x in blocks) + len(block) + 2 > CHUNK_LIMIT:
                    await send_chunks(client, channel, "\n\n".join(blocks))
                    await asyncio.sleep(random.uniform(*SEND_DELAY))
                    blocks = [f"{emoji} {label} | ادامه\n\n"]
                blocks.append(block)

            if len(blocks) > 1:
                await send_chunks(client, channel, "\n\n".join(blocks))
                await asyncio.sleep(random.uniform(*SEND_DELAY))

        if failed:
            failed_text = (
                "⚠️ کانال‌هایی که اطلاعات کاملشان دریافت نشد\n\n"
                + "\n".join(f"@{u}" for u in failed)
            )
            await send_chunks(client, channel, failed_text)
            await asyncio.sleep(random.uniform(*SEND_DELAY))

        await db.set_setting(done_key, "1")
        await db.set_setting("mission.game_channel_directory.v1.channel_id", str(channel.id))
        await db.set_setting("mission.game_channel_directory.v1.total_input", str(len(usernames)))
        await db.set_setting("mission.game_channel_directory.v1.total_processed", str(len(found)))
        await db.set_setting("mission.game_channel_directory.v1.iranian", str(len(iranian)))
        await db.set_setting("mission.game_channel_directory.v1.foreign", str(len(foreign)))
        await db.set_setting("mission.game_channel_directory.v1.failed", str(len(failed)))

        print(
            "GAME_DIRECTORY_MISSION_DONE "
            f"channel={channel.id} total_input={len(usernames)} "
            f"processed={len(found)} iranian={len(iranian)} foreign={len(foreign)} "
            f"failed={len(failed)}"
        )
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
