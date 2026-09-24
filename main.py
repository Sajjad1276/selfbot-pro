from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from contextlib import suppress

from modules.utils.plugin_manager import PluginManager

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
        self.plugin_manager = PluginManager(self.db)
        self._stop_event = asyncio.Event()
        self._http_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        setup_logging(self.settings.log_directory)
        startup_banner()
        await self.db.connect()

        from telethon import TelegramClient
        from telethon.sessions import StringSession

        if self.settings.string_session:
            self.client = TelegramClient(
                StringSession(self.settings.string_session),
                self.settings.api_id,
                self.settings.api_hash,
                sequential_updates=True,
            )
            await self.client.start()
        else:
            Path(self.settings.session_directory).mkdir(parents=True, exist_ok=True)
            self.client = TelegramClient(
                self.settings.session_path,
                self.settings.api_id,
                self.settings.api_hash,
                sequential_updates=True,
            )
            await self.client.start(phone=self.settings.phone or None)

        me = await self.client.get_me()
        await self.db.set_setting("last_account_id", str(me.id))
        await self.db.set_setting("last_account_username", me.username or "")

        await self.scheduler.start()

        if self.settings.http_enabled:
            self._http_task = asyncio.create_task(self._run_http_server())

        from modules.messaging.auto_reply import register as register_auto_reply
        from modules.messaging.secretary import register as register_secretary
        from modules.command_router import register as register_command_router
        from modules.status.rotating_name import register as register_rotating_name
        from modules.status.animated_bio import register as register_animated_bio
        from modules.status.clock_bio import register as register_clock_bio
        from modules.status.time_bio import register as register_time_bio
        from modules.security.saved_deleted import MessageArchive, register_cache

        for register in (
            register_auto_reply,
            register_secretary,
            register_rotating_name,
            register_animated_bio,
            register_clock_bio,
            register_time_bio,
            register_command_router,
        ):
            await register(self.client, self.db, self.settings, self.scheduler)

        self.message_archive = MessageArchive()
        register_cache(self.client, self.message_archive)

        await self._send_log(
            "شروع",
            f"اکانت {me.first_name or ''} با شناسه {me.id} فعال شد.",
        )

        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                asyncio.get_running_loop().add_signal_handler(
                    sig, self._stop_event.set
                )

        await self._stop_event.wait()

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
        if self.client:
            await self.client.disconnect()
        await self.db.close()

    async def _run_http_server(self) -> None:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        import uvicorn

        app = FastAPI(title="SelfBot Pro", docs_url=None, redoc_url=None)

        @app.get("/health")
        async def health() -> JSONResponse:
            connected = bool(self.client and self.client.is_connected())
            return JSONResponse({"status": "ok" if connected else "starting", "telegram": connected})

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
