from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from telethon import events


async def register(client: Any, db: Any, settings: Any, scheduler: Any) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def on_message(event: Any) -> None:
        if not event.is_private or event.sender_id == (await client.get_me()).id:
            return
        enabled = await db.get_setting("autoreply_enabled", "0")
        if enabled != "1":
            return

        text = (event.raw_text or "").strip()
        if not text:
            return

        replies = await db.fetchall(
            "SELECT trigger_keyword, response_text FROM auto_replies WHERE is_active=1"
        )
        lower = text.casefold()
        for row in replies:
            if row["trigger_keyword"].casefold() in lower:
                await event.reply(row["response_text"])
                await db.increment_stat("auto_reply")
                return

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoreply\b"))
    async def command(event: Any) -> None:
        args = event.raw_text.partition(" ")[2].strip()
        if not args:
            await event.edit("دستور: .autoreply on|off یا .autoreply add کلمه | پاسخ")
            return
        parts = args.split(maxsplit=1)
        action = parts[0].lower()
        if action in {"on", "off"}:
            await db.set_setting("autoreply_enabled", "1" if action == "on" else "0")
            await event.edit("پاسخ‌گوی خودکار فعال شد." if action == "on" else "پاسخ‌گوی خودکار خاموش شد.")
            return
        if action == "add" and len(parts) == 2 and "|" in parts[1]:
            keyword, response = [x.strip() for x in parts[1].split("|", 1)]
            if keyword and response:
                await db.execute(
                    "INSERT INTO auto_replies(trigger_keyword,response_text,is_active) VALUES(?,?,1)",
                    (keyword, response),
                )
                await event.edit("قانون پاسخ‌گویی ثبت شد.")
                return
        if action == "list":
            rows = await db.fetchall(
                "SELECT id,trigger_keyword FROM auto_replies ORDER BY id"
            )
            lines = ["پاسخ‌های ثبت‌شده:"]
            lines.extend(f"{row['id']}. {row['trigger_keyword']}" for row in rows)
            await event.edit("\n".join(lines))
            return
        await event.edit("دستور پاسخ‌گوی خودکار نامعتبر است.")
