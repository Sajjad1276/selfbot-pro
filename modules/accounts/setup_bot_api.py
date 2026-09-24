from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp


TELEGRAM_API = "https://api.telegram.org"


@dataclass
class SetupBotEvent:
    bot: "SetupBotApi"
    chat_id: int
    sender_id: int
    message_id: int
    raw_text: str

    async def respond(self, text: str) -> Any:
        return await self.bot.send_message(self.chat_id, text)

    async def delete(self) -> None:
        await self.bot.delete_messages(self.chat_id, [self.message_id])


class SetupBotApi:
    """Small async Telegram Bot API client used only for the setup wizard."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.logger = logging.getLogger("selfbot.setup_bot_api")
        self._handlers: list[tuple[Callable[[SetupBotEvent], Awaitable[None]], re.Pattern[str] | None]] = []
        self._task: asyncio.Task[Any] | None = None
        self._closed = asyncio.Event()
        self._offset = 0
        self._webhook_mode = False

    def add_handler(
        self,
        handler: Callable[[SetupBotEvent], Awaitable[None]],
        pattern: str | None = None,
    ) -> None:
        compiled = re.compile(pattern) if pattern else None
        self._handlers.append((handler, compiled))

    async def start(self, webhook_url: str | None = None) -> None:
        if self._task is not None and not self._task.done():
            return

        self._closed.clear()
        self._webhook_mode = bool(webhook_url)
        if webhook_url:
            await self._call(
                "setWebhook",
                {
                    "url": webhook_url,
                    "allowed_updates": ["message"],
                    "drop_pending_updates": False,
                },
            )
            self.logger.info("Setup Bot webhook enabled: %s", webhook_url)
            return

        self._task = asyncio.create_task(self._poll())

    async def close(self) -> None:
        self._closed.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._webhook_mode:
            with suppress(Exception):
                await self._call("deleteWebhook", {"drop_pending_updates": False})
            self._webhook_mode = False

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        return await self._call("sendMessage", {"chat_id": chat_id, "text": text})

    async def delete_messages(self, chat_id: int, message_ids: list[int]) -> None:
        for message_id in message_ids:
            with suppress(Exception):
                await self._call(
                    "deleteMessage",
                    {"chat_id": chat_id, "message_id": message_id},
                )

    async def send_file(
        self,
        chat_id: int,
        path: Any,
        caption: str = "",
    ) -> dict[str, Any]:
        url = self._url("sendPhoto")
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with open(path, "rb") as file_handle:
                form = aiohttp.FormData()
                form.add_field("chat_id", str(chat_id))
                if caption:
                    form.add_field("caption", caption)
                form.add_field(
                    "photo",
                    file_handle,
                    filename=getattr(path, "name", "qr.png"),
                    content_type="image/png",
                )
                async with session.post(url, data=form) as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400 or not data.get("ok"):
                        raise RuntimeError(
                            f"Telegram Bot API sendPhoto failed: "
                            f"{data.get('description', 'unknown error')}"
                        )
                    return data["result"]

    async def _poll(self) -> None:
        backoff = 2
        while not self._closed.is_set():
            try:
                updates = await self._call(
                    "getUpdates",
                    {
                        "offset": self._offset,
                        "timeout": 25,
                        "allowed_updates": ["message"],
                    },
                    timeout=35,
                )
                backoff = 2
                for update in updates:
                    self._offset = max(self._offset, int(update["update_id"]) + 1)
                    message = update.get("message") or {}
                    from_user = message.get("from") or {}
                    chat = message.get("chat") or {}
                    text = message.get("text")
                    if not text or not from_user.get("id") or not chat.get("id"):
                        continue

                    await self.handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("Setup Bot API polling failed")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        from_user = message.get("from") or {}
        chat = message.get("chat") or {}
        text = message.get("text")
        if not text or not from_user.get("id") or not chat.get("id"):
            return

        event = SetupBotEvent(
            bot=self,
            chat_id=int(chat["id"]),
            sender_id=int(from_user["id"]),
            message_id=int(message["message_id"]),
            raw_text=text,
        )
        await self._dispatch(event)

    async def _dispatch(self, event: SetupBotEvent) -> None:
        for handler, pattern in tuple(self._handlers):
            if pattern and not pattern.search(event.raw_text):
                continue
            try:
                await handler(event)
            except Exception:
                self.logger.exception("Setup bot handler failed")

    def _url(self, method: str) -> str:
        return f"{TELEGRAM_API}/bot{self.token}/{method}"

    async def _call(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        timeout: int = 30,
    ) -> Any:
        url = self._url(method)
        request_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=request_timeout) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json(content_type=None)
                if response.status >= 400 or not data.get("ok"):
                    raise RuntimeError(
                        f"Telegram Bot API {method} failed: "
                        f"{data.get('description', 'unknown error')}"
                    )
                return data.get("result")
