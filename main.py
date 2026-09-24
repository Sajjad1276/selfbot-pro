from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from contextlib import suppress

from modules.utils.plugin_manager import PluginManager
from modules.accounts.manager import AccountManager

from config import get_settings
from modules.utils.database import Database
from modules.utils.helpers import setup_logging, startup_banner
from modules.utils.scheduler import PersistentScheduler


class SelfBotPro:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = Database(self.settings.database_path)
        self.scheduler = PersistentScheduler(self.db, self.settings.timezone)
        self.client = None
        self.setup_bot = None
        self.login_wizard = None
        self.plugin_manager = PluginManager(self.db)
        self.account_manager = AccountManager(self.settings.api_id, self.settings.api_hash, self.settings.session_directory, self.db)
        self._stop_event = asyncio.Event()
        self._http_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        setup_logging(self.settings.log_directory)
        startup_banner()
        await self.db.connect()

        await self.account_manager.connect_saved_sessions()
        if not self.client:
            self.client = self.account_manager.active() or next(iter(self.account_manager.clients.values()), None)

        if not self.client and self.settings.string_session:
            key = self.settings.phone or "primary"
            self.client = await self.account_manager.connect_primary(
                key,
                self.settings.string_session,
                self.settings.phone,
            )

        if not self.client and self.settings.setup_bot_token:
            from telethon import TelegramClient
            from modules.accounts.login_wizard import LoginWizard

            if not self.settings.owner_id:
                raise RuntimeError("برای ورود از طریق ربات، OWNER_ID الزامی است.")
            self.setup_bot = TelegramClient(
                str(Path(self.settings.session_directory) / "setup_bot"),
                self.settings.api_id,
                self.settings.api_hash,
                sequential_updates=True,
            )
            await self.setup_bot.start(bot_token=self.settings.setup_bot_token)
            self.login_wizard = LoginWizard(
                self.setup_bot,
                self.settings.api_id,
                self.settings.api_hash,
                self.settings.session_directory,
                self.settings.owner_id,
                self.db,
                on_login=self._on_user_login,
            )
            await self.login_wizard.register()

        me = await self.client.get_me() if self.client else None
        if me:
            await self.db.set_setting("last_account_id", str(me.id))
            await self.db.set_setting("last_account_username", me.username or "")

        await self.scheduler.start()

        if self.settings.http_enabled:
            self._http_task = asyncio.create_task(self._run_http_server())

        from modules.messaging.auto_reply import register as register_auto_reply
        from modules.messaging.secretary import register as register_secretary
        from modules.messaging.auto_read import register as register_auto_read
        from modules.command_router import register as register_command_router
        from modules.status.rotating_name import register as register_rotating_name
        from modules.status.animated_bio import register as register_animated_bio
        from modules.status.clock_bio import register as register_clock_bio
        from modules.status.time_bio import register as register_time_bio
        from modules.security.saved_deleted import MessageArchive, register_cache

        if self.client:
            await self._register_user_client(
                self.client,
                register_auto_reply,
                register_secretary,
                register_rotating_name,
                register_animated_bio,
                register_clock_bio,
                register_time_bio,
                register_auto_read,
                register_command_router,
                MessageArchive,
                register_cache,
            )
        else:
            self.message_archive = MessageArchive()

        if self.client:
            me = await self.client.get_me()
            name = me.first_name or ""
            await self._send_log("شروع", f"اکانت {name} با شناسه {me.id} فعال شد.")
        elif self.setup_bot:
            await self._send_log("انتظار ورود", "برای اتصال حساب کاربری، ربات راه‌انداز را با /start اجرا کنید.")

        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(
                    sig, self._stop_event.set
                )

        await self._stop_event.wait()

    async def _on_user_login(self, phone: str, session_path: str) -> None:
        from telethon import TelegramClient

        key = phone.replace("+", "").replace(" ", "").replace("-", "")
        client = TelegramClient(session_path, self.settings.api_id, self.settings.api_hash, sequential_updates=True)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return
        self.account_manager.clients[key] = client
        self.account_manager.active_key = key
        self.client = client
        me = await client.get_me()
        await self.db.execute("UPDATE accounts SET is_active=0")
        await self.db.execute(
            "INSERT INTO accounts(phone, session_path, telegram_id, username, is_active) VALUES(?, ?, ?, ?, 1) ON CONFLICT(phone) DO UPDATE SET session_path=excluded.session_path, telegram_id=excluded.telegram_id, username=excluded.username, is_active=1, updated_at=CURRENT_TIMESTAMP",
            (phone, session_path, me.id, me.username),
        )
        from modules.messaging.auto_reply import register as register_auto_reply
        from modules.messaging.secretary import register as register_secretary
        from modules.messaging.auto_read import register as register_auto_read
        from modules.command_router import register as register_command_router
        from modules.status.rotating_name import register as register_rotating_name
        from modules.status.animated_bio import register as register_animated_bio
        from modules.status.clock_bio import register as register_clock_bio
        from modules.status.time_bio import register as register_time_bio
        from modules.security.saved_deleted import MessageArchive, register_cache
        await self._register_user_client(client, register_auto_reply, register_secretary, register_rotating_name, register_animated_bio, register_clock_bio, register_time_bio, register_auto_read, register_command_router, MessageArchive, register_cache)
        await self._send_log("ورود حساب", f"حساب {me.id} وارد و فعال شد.")

    async def _register_user_client(self, client, register_auto_reply, register_secretary, register_rotating_name, register_animated_bio, register_clock_bio, register_time_bio, register_auto_read, register_command_router, message_archive_cls, register_cache) -> None:
        for register in (register_auto_reply, register_secretary, register_rotating_name, register_animated_bio, register_clock_bio, register_time_bio):
            await register(client, self.db, self.settings, self.scheduler)
        await register_auto_read(client, self.db)
        await register_command_router(client, self.db, self.settings, self.scheduler, self.account_manager)
        self.message_archive = message_archive_cls()
        register_cache(client, self.message_archive)
    async def _send_log(self, title: str, text: str) -> None:
        if not self.client or not self.settings.log_channel:
            return
        try:
            await self.client.send_message(
                self.settings.log_channel,
                f"**SelfBot Pro**\n\n{title}\n{text}",
            )
        except Exception:
            pass

    async def stop(self) -> None:
        if self.client:
            await self._send_log("خاموشی", "برنامه در حال خاموش شدن است.")
        await self.scheduler.stop()
        if self._http_task:
            self._http_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._http_task
            self._http_task = None
        await self.account_manager.disconnect_all()
        if self.setup_bot and self.setup_bot.is_connected():
            await self.setup_bot.disconnect()
        self.setup_bot = None
        self.client = None
        await self.db.close()

    async def _run_http_server(self) -> None:
        from fastapi import FastAPI, Request, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn

        app = FastAPI(title="SelfBot Pro", docs_url=None, redoc_url=None)

        def authorized(request) -> bool:
            expected = self.settings.control_api_key
            if not expected:
                return False
            return request.headers.get("X-API-Key") == expected

        @app.get("/health")
        async def health() -> JSONResponse:
            connected = bool(self.client and self.client.is_connected())
            return JSONResponse({"status": "ok" if connected else "starting", "telegram": connected})

        @app.get("/dialogs")
        async def dialogs(request: Request) -> JSONResponse:
            if not authorized(request):
                raise HTTPException(status_code=401, detail="unauthorized")
            items = []
            async for dialog in self.client.iter_dialogs(limit=100):
                items.append({"id": dialog.id, "name": dialog.name, "unread": dialog.unread_count})
            return JSONResponse({"items": items})

        @app.post("/send")
        async def send(payload: dict[str, Any], request: Request) -> JSONResponse:
            if not authorized(request):
                raise HTTPException(status_code=401, detail="unauthorized")
            chat_id = payload.get("chat_id")
            text = payload.get("text")
            if chat_id is None or not isinstance(text, str) or not text.strip():
                raise HTTPException(status_code=400, detail="chat_id و text الزامی هستند")
            message = await self.client.send_message(int(chat_id), text)
            return JSONResponse({"id": message.id, "chat_id": message.chat_id})

        @app.get("/status")
        async def status() -> JSONResponse:
            me = await self.client.get_me() if self.client and self.client.is_connected() else None
            return JSONResponse({
                "status": "ok",
                "telegram_connected": bool(me),
                "telegram_id": me.id if me else None,
                "username": me.username if me else None,
                "scheduled_tasks": self.scheduler.pending_count(),
            })

        config = uvicorn.Config(
            app,
            host=self.settings.http_host,
            port=self.settings.http_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def run(self) -> None:
        try:
            await self.start()
        finally:
            await self.stop()


async def main() -> None:
    app = SelfBotPro()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
