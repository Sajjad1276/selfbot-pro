from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import qrcode
from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError


LOGIN_TIMEOUT_SECONDS = 10 * 60
QR_REFRESH_SECONDS = 90


@dataclass
class LoginState:
    client: TelegramClient
    owner_id: int
    created_at: float
    qr_login: Any | None = None
    qr_message_id: int | None = None
    qr_task: asyncio.Task[Any] | None = None
    awaiting_password: bool = False


class LoginWizard:
    """
    Secure Telegram account login through QR authentication.

    Telegram login codes must not be copied into a Telegram chat. Telethon
    explicitly documents that a login code sent through the Telegram app
    itself immediately expires, so this wizard never requests a login code.
    """

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
        async def start(event: Any) -> None:
            if event.sender_id != self.owner_id:
                return

            state = self.states.get(self.owner_id)
            if state:
                if state.awaiting_password:
                    await event.respond(
                        "QR ورود تأیید شد و رمز دو مرحله‌ای لازم است.\n"
                        "رمز 2FA را همینجا ارسال کن. رمز ذخیره نمی‌شود."
                    )
                else:
                    await event.respond(
                        "یک فرآیند ورود فعال است.\n"
                        "QR نمایش‌داده‌شده را با Telegram حساب مقصد اسکن کن.\n"
                        "برای QR تازه /newcode و برای لغو /cancel را بزن."
                    )
                return

            await self._start_qr_login()

        async def handle_message(event: Any) -> None:
            if event.sender_id != self.owner_id or not event.raw_text:
                return

            text = event.raw_text.strip()

            if text == "/cancel":
                await self._cancel(event)
                return

            if text == "/newcode":
                await self._refresh_qr(event)
                return

            state = self.states.get(self.owner_id)
            if not state:
                return

            if state.awaiting_password:
                password = event.raw_text.strip()
                if not password:
                    await self._delete_message(event)
                    return
                try:
                    await self._finish_password(event, state, password)
                except PasswordHashInvalidError:
                    await event.respond(
                        "رمز دو مرحله‌ای نادرست است. دوباره وارد کن یا /cancel بزن."
                    )
                    await self._delete_message(event)
                except Exception:
                    self.logger.exception("QR 2FA login flow failed")
                    await event.respond(
                        "ورود دومرحله‌ای انجام نشد. خطای فنی ثبت شد. "
                        "دوباره رمز را وارد کن یا /cancel بزن."
                    )
                    await self._delete_message(event)

        self.bot.add_handler(start, pattern=r"^/start$")
        self.bot.add_handler(handle_message)

    async def _start_qr_login(self) -> None:
        await self._reset_state(delete_session=True)

        session_base = self.session_directory / "pending_login"
        client = TelegramClient(
            str(session_base),
            self.api_id,
            self.api_hash,
            sequential_updates=True,
        )

        try:
            await client.connect()
            qr_login = await client.qr_login()
        except Exception:
            await client.disconnect()
            self.logger.exception("Could not start Telegram QR login")
            await self.bot.send_message(
                self.owner_id,
                "شروع ورود با QR انجام نشد. خطای فنی در لاگ ثبت شد."
            )
            return

        state = LoginState(
            client=client,
            owner_id=self.owner_id,
            created_at=asyncio.get_running_loop().time(),
            qr_login=qr_login,
        )
        self.states[self.owner_id] = state

        await self._send_qr(state)
        state.qr_task = asyncio.create_task(self._wait_for_qr(state))

        await self.db.set_setting("login_2fa_pending", "0")

    async def _send_qr(self, state: LoginState) -> None:
        qr_path = self.session_directory / "pending_login_qr.png"

        with suppress(Exception):
            if state.qr_message_id:
                await self.bot.delete_messages(self.owner_id, [state.qr_message_id])

        try:
            image = qrcode.make(state.qr_login.url)
            image.save(qr_path)

            message = await self.bot.send_file(
                self.owner_id,
                qr_path,
                caption=(
                    "ورود به SelfBot Pro\n\n"
                    "1) Telegram حساب مقصد را باز کن.\n"
                    "2) Settings → Devices → Link Desktop Device را بزن.\n"
                    "3) QR همین پیام را اسکن کن.\n\n"
                    "کد ورود Telegram را در چت ارسال نکن.\n"
                    "برای QR تازه /newcode و برای لغو /cancel."
                ),
            )
            state.qr_message_id = message.id
        except Exception:
            self.logger.exception("Could not send QR code")
            await self.bot.send_message(
                self.owner_id,
                "ساخت یا ارسال QR انجام نشد. خطای فنی در لاگ ثبت شد."
            )
        finally:
            with suppress(Exception):
                if qr_path.exists():
                    qr_path.unlink()

    async def _wait_for_qr(self, state: LoginState) -> None:
        deadline = asyncio.get_running_loop().time() + LOGIN_TIMEOUT_SECONDS

        while self.states.get(self.owner_id) is state:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await self._expire_state(state)
                return

            try:
                user = await state.qr_login.wait(timeout=min(QR_REFRESH_SECONDS, remaining))
                await self._complete(state, user)
                return
            except asyncio.TimeoutError:
                if self.states.get(self.owner_id) is not state:
                    return
                try:
                    await state.qr_login.recreate()
                    await self._send_qr(state)
                except Exception:
                    self.logger.exception("Could not refresh Telegram QR login")
                    await self._expire_state(state)
                    return
            except SessionPasswordNeededError:
                if self.states.get(self.owner_id) is not state:
                    return

                state.awaiting_password = True
                await self.db.set_setting("login_2fa_pending", "1")
                await self.bot.send_message(
                    self.owner_id,
                    "QR با موفقیت تأیید شد. حساب شما رمز دو مرحله‌ای دارد.\n"
                    "رمز 2FA را همینجا ارسال کن. رمز ذخیره نمی‌شود."
                )
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("QR Telegram login failed")
                await self._safe_send(
                    "ورود با QR ناموفق بود. خطای فنی ثبت شد. "
                    "دوباره /start را بزن."
                )
                await self._reset_state(delete_session=True)
                return

    async def _finish_password(
        self,
        event: Any,
        state: LoginState,
        password: str,
    ) -> None:
        if self.states.get(self.owner_id) is not state:
            await self._delete_message(event)
            return

        user = await state.client.sign_in(password=password)
        await self._complete(state, user)
        await self._delete_message(event)

    async def _complete(self, state: LoginState, user: Any) -> None:
        session_id = re.sub(r"\D+", "", str(getattr(user, "phone", "") or ""))
        if not session_id:
            session_id = str(user.id)

        final_path = self.session_directory / session_id
        old_path = self.session_directory / "pending_login.session"
        final_session = final_path.with_suffix(".session")

        current_task = asyncio.current_task()
        if state.qr_task and state.qr_task is not current_task:
            state.qr_task.cancel()
            with suppress(asyncio.CancelledError):
                await state.qr_task

        with suppress(Exception):
            if state.qr_message_id:
                await self.bot.delete_messages(self.owner_id, [state.qr_message_id])

        await state.client.disconnect()

        with suppress(FileNotFoundError):
            if final_session.exists():
                final_session.unlink()
        if old_path.exists():
            old_path.replace(final_session)

        self.states.pop(self.owner_id, None)
        await self.db.set_setting(
            "last_logged_phone",
            str(getattr(user, "phone", "") or user.id),
        )
        await self.db.set_setting("login_2fa_pending", "0")

        if self.on_login:
            await self.on_login(
                str(getattr(user, "phone", "") or user.id),
                str(final_path),
            )

        name = (getattr(user, "first_name", "") or "").strip()
        label = f"حساب {name}" if name else "حساب کاربری"
        await self._safe_send(f"ورود انجام شد. {label} آماده استفاده است.")

    async def _expire_state(self, state: LoginState) -> None:
        if self.states.get(self.owner_id) is not state:
            return

        await self._reset_state(delete_session=True)
        await self._safe_send(
            "مهلت ورود با QR تمام شد. دوباره /start را بزن."
        )

    async def _cancel(self, event: Any) -> None:
        await self._reset_state(delete_session=True)
        await self.db.set_setting("login_2fa_pending", "0")
        await event.respond("فرآیند ورود لغو شد.")
        await self._delete_message(event)

    async def _refresh_qr(self, event: Any) -> None:
        state = self.states.get(self.owner_id)
        if not state:
            await event.respond("فرآیند ورود فعالی وجود ندارد. ابتدا /start را بزن.")
            await self._delete_message(event)
            return

        await self._reset_state(delete_session=True)
        await self._start_qr_login()
        await self._delete_message(event)

    async def _reset_state(self, delete_session: bool = False) -> None:
        state = self.states.pop(self.owner_id, None)
        current_task = asyncio.current_task()

        if state:
            if state.qr_task and state.qr_task is not current_task:
                state.qr_task.cancel()
                with suppress(asyncio.CancelledError):
                    await state.qr_task

            with suppress(Exception):
                if state.qr_message_id:
                    await self.bot.delete_messages(self.owner_id, [state.qr_message_id])

            with suppress(Exception):
                await state.client.disconnect()

        if delete_session:
            for filename in (
                "pending_login",
                "pending_login.session",
                "pending_login.session-journal",
                "pending_login_qr.png",
            ):
                path = self.session_directory / filename
                with suppress(Exception):
                    if path.exists():
                        path.unlink()

    async def _safe_send(self, text: str) -> None:
        with suppress(Exception):
            await self.bot.send_message(self.owner_id, text)

    async def _delete_message(self, event: Any) -> None:
        with suppress(Exception):
            await event.delete()
