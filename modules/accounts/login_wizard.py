from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)


@dataclass
class LoginState:
    phone: str
    client: TelegramClient
    phone_code_hash: str
    owner_id: int
    created_at: float
    awaiting_password: bool = False


class LoginWizard:
    def __init__(
        self,
        bot: TelegramClient,
        api_id: int,
        api_hash: str,
        session_directory: str,
        owner_id: int,
        db: Any,
        on_login: Any | None = None,
    ) -> None:
        self.bot = bot
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_directory = Path(session_directory)
        self.session_directory.mkdir(parents=True, exist_ok=True)
        self.owner_id = owner_id
        self.db = db
        self.on_login = on_login
        self.states: dict[int, LoginState] = {}
        self.logger = logging.getLogger("selfbot.login")

    async def register(self) -> None:
        @self.bot.on(events.NewMessage(pattern=r"^/start$"))
        async def start(event: Any) -> None:
            if event.sender_id != self.owner_id:
                return
            await event.respond(
                "SelfBot Pro آماده است.\n\n"
                "برای ورود حساب Telegram، شماره را با فرمت +98912xxxxxxx ارسال کن."
            )

        @self.bot.on(events.NewMessage())
        async def handle_message(event: Any) -> None:
            if event.sender_id != self.owner_id or not event.raw_text:
                return

            text = event.raw_text.strip()
            if text == "/cancel":
                state = self.states.pop(self.owner_id, None)
                if state:
                    await state.client.disconnect()
                await event.respond("فرآیند ورود لغو شد.")
                return

            state = self.states.get(self.owner_id)
            if not state:
                if not text.startswith("+"):
                    return
                await self._request_code(event, text)
                return

            try:
                if state.awaiting_password:
                    await self._finish_password(event, state, text)
                else:
                    await self._finish_login(event, state, text)
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                await event.respond("کد نادرست یا منقضی است. دوباره کد را ارسال کن یا /cancel بزن.")
            except SessionPasswordNeededError:
                await self.db.set_setting("login_2fa_pending", "1")
                await event.respond("ورود این حساب نیاز به رمز دو مرحله‌ای دارد. رمز 2FA را ارسال کن.")
                self.states[self.owner_id] = state

    async def _request_code(self, event: Any, phone: str) -> None:
        client = TelegramClient(
            str(self.session_directory / "pending_login"),
            self.api_id,
            self.api_hash,
        )
        await client.connect()
        sent = await client.send_code_request(phone)
        self.states[self.owner_id] = LoginState(
            phone=phone,
            client=client,
            phone_code_hash=sent.phone_code_hash,
            owner_id=self.owner_id,
            created_at=asyncio.get_running_loop().time(),
        )
        await event.respond(
            "کد ورود ارسال شد. کد Telegram را همینجا ارسال کن.\n"
            "کد را در جای دیگری ذخیره نکن."
        )

    async def _finish_password(self, event: Any, state: LoginState, password: str) -> None:
        user = await state.client.sign_in(
            phone=state.phone,
            password=password,
            phone_code_hash=state.phone_code_hash,
        )
        await self._complete(event, state, user)

    async def _complete(self, event: Any, state: LoginState, user: Any) -> None:
        safe_phone = state.phone.replace("+", "").replace(" ", "").replace("-", "")
        final_path = self.session_directory / safe_phone
        await state.client.disconnect()
        old_path = self.session_directory / "pending_login.session"
        if old_path.exists():
            old_path.replace(final_path.with_suffix(".session"))

        self.states.pop(self.owner_id, None)
        await self.db.set_setting("last_logged_phone", state.phone)
        if self.on_login:
            await self.on_login(state.phone, str(final_path))
        await event.respond(
            f"ورود انجام شد. حساب {getattr(user, 'first_name', '') or ''} آماده استفاده است."
        )

    async def _finish_login(self, event: Any, state: LoginState, text: str) -> None:
        try:
            user = await state.client.sign_in(
                phone=state.phone,
                code=text,
                phone_code_hash=state.phone_code_hash,
            )
        except SessionPasswordNeededError:
            password = text
            user = await state.client.sign_in(
                phone=state.phone,
                password=password,
                phone_code_hash=state.phone_code_hash,
            )

        await self._complete(event, state, user)
