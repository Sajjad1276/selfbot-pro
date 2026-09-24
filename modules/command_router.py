from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from telethon import events

from modules.ai.gemini import GeminiChat
from modules.ai.translator import translate
from modules.finance.calculator import calculate
from modules.finance.currency import CurrencyClient
from modules.friends.friend_enemy import choose_response, set_status
from modules.info.account_stats import collect_account_stats
from modules.info.id_finder import resolve_id
from modules.status.fonts import convert_font
from modules.utils.helpers import owner_only, parse_duration, split_command


class CommandRouter:
    def __init__(self, client: Any, db: Any, settings: Any, scheduler: Any, accounts: Any = None) -> None:
        self.client = client
        self.db = db
        self.settings = settings
        self.scheduler = scheduler
        self.currency = CurrencyClient()
        self.accounts = accounts
        self.gemini = (
            GeminiChat(settings.gemini_api_key, settings.gemini_model)
            if settings.gemini_api_key
            else None
        )

    async def register(self) -> None:
        @self.client.on(events.NewMessage(incoming=True))
        async def ai_handler(event: Any) -> None:
            if not event.is_private or not self.gemini or not event.raw_text:
                return
            if await self.db.get_setting(f"ai:{event.chat_id}", "0") != "1":
                return
            history = await self.db.get_ai_memory(event.chat_id, 50)
            answer = await self.gemini.reply(history, event.raw_text, self.settings.default_lang)
            await self.db.save_ai_message(event.chat_id, "user", event.raw_text)
            await self.db.save_ai_message(event.chat_id, "assistant", answer)
            await event.reply(answer)

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

        if command == "bio":
            if not owner_only(self.settings.owner_id, event.sender_id):
                await event.edit("این فرمان فقط برای مالک است.")
                return
            from modules.status.animated_bio import set_bio
            parts = args.rsplit(" interval:", 1)
            texts = [x.strip() for x in parts[0].split("|") if x.strip()]
            interval = float(parts[1]) if len(parts) == 2 else 30.0
            await set_bio(self.client, self.db, self.scheduler, texts, interval)
            await event.edit("Bio چرخشی ثبت شد.")
            return

        if command == "name":
            if not owner_only(self.settings.owner_id, event.sender_id):
                await event.edit("این فرمان فقط برای مالک است.")
                return
            from modules.status.rotating_name import set_name
            parts = args.rsplit(" interval:", 1)
            names = [x.strip() for x in parts[0].split("|") if x.strip()]
            interval = float(parts[1]) if len(parts) == 2 else 30.0
            await set_name(self.client, self.db, self.scheduler, names, interval)
            await event.edit("نام چرخشی ثبت شد.")
            return

        if command == "clock":
            if not owner_only(self.settings.owner_id, event.sender_id):
                await event.edit("این فرمان فقط برای مالک است.")
                return
            await self.db.set_setting("clock_bio_enabled", "1" if args.lower() == "on" else "0")
            await event.edit("ساعت Bio به‌روزرسانی می‌شود." if args.lower() == "on" else "ساعت Bio خاموش شد.")
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

        if command == "account":
            await self._account(event, args)
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
            if not self.gemini:
                await event.edit("GEMINI_API_KEY تنظیم نشده است.")
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
            from modules.utils.plugin_manager import PluginManager
            manager = PluginManager(self.db)
            if args == "list":
                rows = await manager.list_plugins()
                await event.edit("\n".join(f"{r['name']}: {'فعال' if r['enabled'] else 'خاموش'}" for r in rows) or "افزونه‌ای ثبت نشده است.")
                return
            await event.edit("فرمان افزونه: .plugin list")
            return

    async def _account(self, event: Any, args: str) -> None:
        if not self.accounts:
            await event.edit("مدیریت حساب فعال نیست.")
            return
        parts = args.split()
        if not parts:
            await event.edit("استفاده: .account list یا .account switch شماره")
            return
        if parts[0] == "list":
            rows = await self.accounts.list_accounts()
            await event.edit("\n".join(
                f"{r['phone']} | {r['username'] or '-'} | {'فعال' if r['is_active'] else 'متصل'}"
                for r in rows
            ) or "حسابی ثبت نشده است.")
            return
        if parts[0] == "switch" and len(parts) == 2:
            self.client = self.accounts.switch(parts[1])
            await self.db.execute("UPDATE accounts SET is_active=0")
            await self.db.execute("UPDATE accounts SET is_active=1 WHERE phone=?", (parts[1],))
            await event.edit("حساب فعال تغییر کرد.")
            return
        await event.edit("دستور حساب نامعتبر است.")

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


async def register(client: Any, db: Any, settings: Any, scheduler: Any, accounts: Any = None) -> None:
    router = CommandRouter(client, db, settings, scheduler, accounts)
    scheduler.register_handler(
        "send_message",
        lambda chat_id, text: client.send_message(chat_id, text),
    )
    await router.register()
