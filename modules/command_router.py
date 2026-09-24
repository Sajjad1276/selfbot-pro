from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from telethon import events

from modules.ai.chatbot import ClaudeChat
from modules.ai.translator import translate
from modules.finance.calculator import calculate
from modules.finance.currency import CurrencyClient
from modules.friends.friend_enemy import choose_response, set_status
from modules.info.account_stats import collect_account_stats
from modules.info.id_finder import resolve_id
from modules.status.fonts import convert_font
from modules.utils.helpers import owner_only, parse_duration, split_command


class CommandRouter:
    def __init__(self, client: Any, db: Any, settings: Any, scheduler: Any) -> None:
        self.client = client
        self.db = db
        self.settings = settings
        self.scheduler = scheduler
        self.currency = CurrencyClient()
        self.claude = (
            ClaudeChat(settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )

    async def register(self) -> None:
        @self.client.on(events.NewMessage(outgoing=True))
        async def handler(event: Any) -> None:
            if not event.raw_text:
                return
            command, args = split_command(event.raw_text, self.settings.prefix)
            if not command:
                return
            try:
                await self.dispatch(event, command, args)
            except Exception as exc:
                await event.edit(f"خطا: {exc}")

    async def dispatch(self, event: Any, command: str, args: str) -> None:
        if command == "help":
            await event.edit(
                "SelfBot Pro\n\n"
                ".font سبک متن\n"
                ".calc عبارت\n"
                ".tr en متن\n"
                ".weather شهر\n"
                ".info\n"
                ".id شناسه یا نام کاربری\n"
                ".friend add شناسه\n"
                ".enemy add شناسه\n"
                ".ai on|off\n"
                ".schedule list\n"
                ".plugin list"
            )
            return

        if command == "font":
            parts = args.split(maxsplit=1)
            if len(parts) != 2:
                await event.edit("استفاده: .font bold متن")
                return
            await event.edit(convert_font(parts[1], parts[0]))
            return

        if command == "calc":
            await event.edit(str(calculate(args)))
            return

        if command == "tr":
            parts = args.split(maxsplit=1)
            if len(parts) != 2:
                await event.edit("استفاده: .tr en متن")
                return
            await event.edit(translate(parts[1], target=parts[0]))
            return

        if command == "weather":
            from modules.fun.weather import get_weather
            data = await get_weather(args)
            await event.edit(
                f"هوا در {data['city']}\n"
                f"دما: {data['temperature_c']}°C\n"
                f"احساس: {data['feels_like_c']}°C\n"
                f"وضعیت: {data['description']}\n"
                f"رطوبت: {data['humidity']}%"
            )
            return

        if command == "info":
            stats = await collect_account_stats(self.client)
            await event.edit("\n".join(f"{k}: {v}" for k, v in stats.items()))
            return

        if command == "id":
            data = await resolve_id(self.client, args)
            await event.edit("\n".join(f"{k}: {v}" for k, v in data.items()))
            return

        if command in {"friend", "enemy"}:
            parts = args.split()
            if len(parts) != 2 or parts[0] != "add" or not parts[1].lstrip("-").isdigit():
                await event.edit(f"استفاده: .{command} add شناسه")
                return
            await set_status(self.db, int(parts[1]), command)
            await event.edit("وضعیت کاربر ثبت شد.")
            return

        if command == "ai":
            if not self.claude:
                await event.edit("ANTHROPIC_API_KEY تنظیم نشده است.")
                return
            if args.lower() in {"on", "off"}:
                await self.db.set_setting(f"ai:{event.chat_id}", "1" if args.lower() == "on" else "0")
                await event.edit("حالت AI فعال شد." if args.lower() == "on" else "حالت AI خاموش شد.")
                return
            await event.edit("استفاده: .ai on یا .ai off")
            return

        if command == "schedule":
            if not owner_only(self.settings.owner_id, event.sender_id):
                await event.edit("این فرمان فقط برای مالک است.")
                return
            await self._schedule(event, args)
            return

        if command == "plugin":
            if not owner_only(self.settings.owner_id, event.sender_id):
                await event.edit("این فرمان فقط برای مالک است.")
                return
            await event.edit("مدیریت افزونه‌ها از طریق PluginManager انجام می‌شود.")
            return

    async def _schedule(self, event: Any, args: str) -> None:
        parts = shlex.split(args)
        if not parts:
            await event.edit("استفاده: .schedule list")
            return
        if parts[0] == "list":
            rows = await self.scheduler.list_tasks()
            if not rows:
                await event.edit("زمان‌بندی فعالی وجود ندارد.")
                return
            await event.edit("\n".join(f"{r['id']}: {r['task_type']} {r['trigger']}" for r in rows))
            return
        if parts[0] == "delete" and len(parts) == 2:
            await self.scheduler.remove(int(parts[1]))
            await event.edit("زمان‌بندی حذف شد.")
            return
        if parts[0] == "add" and len(parts) >= 3:
            text = parts[1]
            if parts[2].startswith("every:"):
                seconds = parse_duration(parts[2].split(":", 1)[1])
                await self.scheduler.add_interval(
                    "send_message",
                    seconds,
                    {"chat_id": event.chat_id, "text": text},
                )
                await event.edit("زمان‌بندی ثبت شد.")
                return
        await event.edit("دستور زمان‌بندی نامعتبر است.")


async def register(client: Any, db: Any, settings: Any, scheduler: Any) -> None:
    router = CommandRouter(client, db, settings, scheduler)
    scheduler.register_handler(
        "send_message",
        lambda chat_id, text: client.send_message(chat_id, text),
    )
    await router.register()
