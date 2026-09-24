from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

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
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        setup_logging(self.settings.log_directory)
        startup_banner()
        await self.db.connect()

        from telethon import TelegramClient

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

        from modules.messaging.auto_reply import register as register_auto_reply
        from modules.messaging.secretary import register as register_secretary
        from modules.status.rotating_name import register as register_rotating_name
        from modules.status.animated_bio import register as register_animated_bio

        for register in (
            register_auto_reply,
            register_secretary,
            register_rotating_name,
            register_animated_bio,
        ):
            await register(self.client, self.db, self.settings, self.scheduler)

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
        if self.client:
            await self.client.disconnect()
        await self.db.close()

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
