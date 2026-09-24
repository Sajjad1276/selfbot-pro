from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from datetime import datetime, timezone
from telethon.errors import FloodWaitError


QUERIES = [
    "looking for telegram bot",
    "need a bot",
    "recommend bot",
    "telegram bot needed",
    "need automation",
    "bot for group",
    "bot for channel",
    "download bot",
    "pdf bot",
    "file bot",
    "reminder bot",
    "translation bot",
    "AI bot",
    "search bot",
    "price tracker bot",
    "notification bot",
    "anonymous bot",
    "admin bot",
    "utility bot",
    "telegram tools",
]


async def run_bringstorm_once(client, db) -> bool:
    """Research Telegram demand through the logged-in user account.

    Enabled only when BRINGSTORM_ENABLED=1. A DB guard prevents repeat runs.
    Results are sent only to Saved Messages.
    """
    if os.getenv("BRINGSTORM_ENABLED", "0") != "1":
        return False

    run_id = os.getenv("BRINGSTORM_RUN_ID", "1")
    setting_key = f"bringstorm_completed:{run_id}"
    if await db.get_setting(setting_key, "0") == "1":
        return False

    await client.send_message("me", "Bringstorm شروع شد. جست‌وجوی تقاضا در Telegram در حال انجام است.")

    findings = defaultdict(list)
    seen = set()

    for query in QUERIES:
        try:
            async for msg in client.iter_messages(None, search=query, limit=25, wait_time=1):
                chat = getattr(msg, "chat", None)
                if not chat:
                    continue
                username = getattr(chat, "username", None)
                title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(getattr(chat, "id", ""))
                text = (msg.raw_text or "").replace("\n", " ").strip()
                key = (getattr(chat, "id", None), query)
                if key in seen:
                    continue
                seen.add(key)
                findings[query].append({
                    "title": title,
                    "username": username,
                    "text": text[:280],
                    "members": getattr(chat, "participants_count", None),
                })
        except FloodWaitError as exc:
            await asyncio.sleep(min(exc.seconds, 30))
        except Exception:
            continue

    lines = [
        "BRINGSTORM | Telegram demand research",
        f"زمان: {datetime.now(timezone.utc).isoformat()}",
        "",
        "هدف: پیدا کردن نیازهای تکرارشونده که با یک ربات Telegram حل شوند و MVP آنها هزینه اولیه پایین داشته باشد.",
        "",
    ]

    for query, rows in findings.items():
        if not rows:
            continue
        lines.append(f"QUERY: {query}")
        for row in rows[:12]:
            handle = f"@{row['username']}" if row["username"] else "-"
            members = f" | members={row['members']}" if row["members"] else ""
            lines.append(f"- {row['title']} | {handle}{members}")
            if row["text"]:
                lines.append(f"  {row['text']}")
        lines.append("")

    if len(lines) <= 5:
        lines.append("نتیجه قابل استفاده‌ای از جست‌وجوی عمومی پیدا نشد.")

    # Keep Saved Messages readable and avoid Telegram message-size limits.
    report = "\n".join(lines)
    for start in range(0, len(report), 3500):
        await client.send_message("me", report[start:start + 3500])

    print(report, flush=True)
    await db.set_setting(setting_key, "1")
    return True
