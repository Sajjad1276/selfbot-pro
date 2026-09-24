from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.sessions import StringSession


class AccountManager:
    def __init__(self, api_id: int, api_hash: str, session_dir: str, db: Any) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_dir = Path(session_dir)
        self.db = db
        self.clients: dict[str, TelegramClient] = {}
        self.active_key: str | None = None

    async def connect_primary(self, key: str, string_session: str | None, phone: str | None) -> TelegramClient:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if string_session:
            client = TelegramClient(
                StringSession(string_session),
                self.api_id,
                self.api_hash,
                sequential_updates=True,
            )
            await client.start()
        else:
            name = key.replace("+", "").replace(" ", "").replace("-", "") or "default"
            client = TelegramClient(
                str(self.session_dir / name),
                self.api_id,
                self.api_hash,
                sequential_updates=True,
            )
            await client.start(phone=phone or None)
        self.clients[key] = client
        self.active_key = key
        me = await client.get_me()
        await self.db.execute(
            """
            INSERT INTO accounts(phone, session_path, telegram_id, username, is_active)
            VALUES(?, ?, ?, ?, 1)
            ON CONFLICT(phone) DO UPDATE SET
                session_path=excluded.session_path,
                telegram_id=excluded.telegram_id,
                username=excluded.username,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, str(self.session_dir / key), me.id, me.username),
        )
        return client

    async def connect_saved_sessions(self) -> list[str]:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        connected = []
        for path in sorted(self.session_dir.glob("*.session")):
            key = path.stem
            if key in self.clients:
                continue
            try:
                client = TelegramClient(
                    str(path.with_suffix("")),
                    self.api_id,
                    self.api_hash,
                    sequential_updates=True,
                )
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    continue
                self.clients[key] = client
                me = await client.get_me()
                await self.db.execute(
                    """
                    INSERT INTO accounts(phone, session_path, telegram_id, username, is_active)
                    VALUES(?, ?, ?, ?, 0)
                    ON CONFLICT(phone) DO UPDATE SET
                        session_path=excluded.session_path,
                        telegram_id=excluded.telegram_id,
                        username=excluded.username,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (key, str(path.with_suffix("")), me.id, me.username),
                )
                connected.append(key)
            except Exception:
                continue
        return connected

    async def list_accounts(self) -> list[dict[str, object]]:
        return await self.db.fetchall(
            "SELECT phone, telegram_id, username, is_active FROM accounts ORDER BY phone"
        )

    def active(self) -> TelegramClient | None:
        return self.clients.get(self.active_key or "")

    def switch(self, key: str) -> TelegramClient:
        if key not in self.clients:
            raise KeyError("حساب موردنظر متصل نیست.")
        self.active_key = key
        return self.clients[key]

    async def disconnect_all(self) -> None:
        for client in self.clients.values():
            if client.is_connected():
                await client.disconnect()
        self.clients.clear()
        self.active_key = None
