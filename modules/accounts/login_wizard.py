from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)


LOGIN_TIMEOUT_SECONDS = 10 * 60
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


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
            state = self.states.get(self.owner_id)
            if state:
                step = "رمز دو مرحله‌ای" if state.awaiting_password else "کد ورود"
                await event.respond(
                    f"یک فرآیند ورود فعال است. مرحله فعلی: {step}\n"
                    "برای شروع مجدد، /cancel را بفرست."
                )
                return
            await event.respond(
                "SelfBot Pro آماده است.\n\n"
                "شماره حساب Telegram را با فرمت بین‌المللی ارسال کن."
            )

        @self.bot.on(events.NewMessage())
        async def handle_message(event: Any) -> None:
            if event.sender_id != self.owner_id or not event.raw_text:
                return

            raw_text = event.raw_text
            text = raw_text.strip()

            if text == "/cancel":
                await self._cancel(event)
                return

            state = self.states.get(self.owner_id)
            if not state:
                if text.startswith("+"):
                    await self._request_code(event, text)
                return

            if self._expired(state):
                await self._reset_state()
                await event.respond("مهلت ورود تمام شد. دوباره /start را بزن.")
                await self._delete_message(event)
                return

            try:
                if state.awaiting_password:
                    await self._finish_password(event, state, text)
                else:
                    code = self._normalize_code(raw_text)
                    if not code:
                        await event.respond(
                            "کد نامعتبر است. فقط عددهای کد Telegram را ارسال کن."
                        )
                        await self._delete_message(event)
                        return
                    if len(code) < 4:
                        await event.respond(
                            "کد ناقص دریافت شد. همه رقم‌های کد Telegram را یکجا ارسال کن."
                        )
                        await self._delete_message(event)
                        return
                    await self._finish_login(event, state, code)
            except SessionPasswordNeededError:
                state.awaiting_password = True
                await self.db.set_setting("login_2fa_pending", "1")
                await event.respond(
                    "این حساب رمز دو مرحله‌ای دارد. رمز 2FA را همینجا ارسال کن.\n"
                    "رمز ذخیره نمی‌شود."
                )
                await self._delete_message(event)
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                await event.respond(
                    "کد Telegram نادرست یا منقضی است. کد کامل را دوباره ارسال کن یا /cancel بزن."
                )
                await self._delete_message(event)
            except PasswordHashInvalidError:
                await event.respond(
                    "رمز دو مرحله‌ای نادرست است. دوباره وارد کن یا /cancel بزن."
                )
                await self._delete_message(event)
            except Exception:
                self.logger.exception("Login flow failed")
                await event.respond(
                    "ورود انجام نشد. خطای فنی ثبت شد. /cancel و سپس دوباره تلاش کن."
                )
                await self._delete_message(event)

    @staticmethod
    def _normalize_code(value: str) -> str:
        normalized = value.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
        return re.sub(r"\D", "", normalized)

    def _expired(self, state: LoginState) -> bool:
        return (
            asyncio.get_running_loop().time() - state.created_at
            > LOGIN_TIMEOUT_SECONDS
        )

    async def _request_code(self, event: Any, phone: str) -> None:
        client = TelegramClient(
            str(self.session_directory / "pending_login"),
            self.api_id,
            self.api_hash,
        )
        try:
            await client.connect()
            sent = await client.send_code_request(phone)
        except PhoneNumberInvalidError:
            await client.disconnect()
            await event.respond(
                "شماره Telegram معتبر نیست. شماره را با فرمت بین‌المللی ارسال کن."
            )
            await self._delete_message(event)
            return
        except Exception:
            await client.disconnect()
            self.logger.exception("Could not request Telegram login code")
            await event.respond("ارسال کد ورود انجام نشد. دوباره تلاش کن.")
            await self._delete_message(event)
            return

        self.states[self.owner_id] = LoginState(
            phone=phone,
            client=client,
            phone_code_hash=sent.phone_code_hash,
            owner_id=self.owner_id,
            created_at=asyncio.get_running_loop().time(),
        )
        await event.respond(
            "کد ورود ارسال شد. کد کامل Telegram را همینجا ارسال کن.\n"
            "اگر کد به شکل چند رقم با فاصله نمایش داده شد، همان را ارسال کن."
        )
        await self._delete_message(event)

    async def _finish_password(
        self,
        event: Any,
        state: LoginState,
        password: str,
    ) -> None:
        user = await state.client.sign_in(password=password)
        await self._complete(event, state, user)

    async def _finish_login(
        self,
        event: Any,
        state: LoginState,
        code: str,
    ) -> None:
        user = await state.client.sign_in(
            phone=state.phone,
            code=code,
            phone_code_hash=state.phone_code_hash,
        )
        await self._complete(event, state, user)

    async def _complete(self, event: Any, state: LoginState, user: Any) -> None:
        safe_phone = state.phone.replace("+", "").replace(" ", "").replace("-", "")
        final_path = self.session_directory / safe_phone
        old_path = self.session_directory / "pending_login.session"

        await state.client.disconnect()
        if old_path.exists():
            old_path.replace(final_path.with_suffix(".session"))

        self.states.pop(self.owner_id, None)
        await self.db.set_setting("last_logged_phone", state.phone)
        await self.db.set_setting("login_2fa_pending", "0")

        if self.on_login:
            await self.on_login(state.phone, str(final_path))

        name = (getattr(user, "first_name", "") or "").strip()
        label = f"حساب {name}" if name else "حساب کاربری"
        await event.respond(f"ورود انجام شد. {label} آماده استفاده است.")
        await self._delete_message(event)

    async def _cancel(self, event: Any) -> None:
        await self._reset_state()
        await self.db.set_setting("login_2fa_pending", "0")
        await event.respond("فرآیند ورود لغو شد.")
        await self._delete_message(event)

    async def _reset_state(self) -> None:
        state = self.states.pop(self.owner_id, None)
        if state:
            with suppress(Exception):
                await state.client.disconnect()

    async def _delete_message(self, event: Any) -> None:
        with suppress(Exception):
            await event.delete()
