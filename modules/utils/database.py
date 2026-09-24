from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    phone TEXT PRIMARY KEY,
    session_path TEXT NOT NULL,
    telegram_id INTEGER,
    username TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friends (
    user_id INTEGER PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('friend','enemy','neutral')),
    added_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auto_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_keyword TEXT NOT NULL,
    response_text TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS saved_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    sender_id INTEGER,
    text TEXT,
    media_path TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    edited INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS birthdays (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    birth_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('delete','warn','ban')),
    UNIQUE(chat_id, word)
);

CREATE TABLE IF NOT EXISTS locks (
    chat_id INTEGER NOT NULL,
    lock_type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    custom_message TEXT,
    PRIMARY KEY(chat_id, lock_type)
);

CREATE TABLE IF NOT EXISTS rotating_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('bio','name','emoji')),
    texts_json TEXT NOT NULL,
    interval REAL NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 0,
    UNIQUE(type)
);

CREATE TABLE IF NOT EXISTS stats (
    event_type TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    trigger TEXT NOT NULL,
    interval_seconds REAL,
    cron_json TEXT,
    next_run_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_memory (
    chat_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(chat_id, position)
);

CREATE TABLE IF NOT EXISTS plugins (
    name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    loaded_at TEXT,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    action TEXT NOT NULL,
    error TEXT NOT NULL,
    traceback TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    def _require(self) -> aiosqlite.Connection:
        if not self.conn:
            raise RuntimeError("اتصال دیتابیس برقرار نیست.")
        return self.conn

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        conn = self._require()
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.lastrowid or 0

    async def executemany(
        self, query: str, rows: list[tuple[Any, ...]]
    ) -> None:
        conn = self._require()
        await conn.executemany(query, rows)
        await conn.commit()

    async def fetchone(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        conn = self._require()
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetchall(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        conn = self._require()
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = await self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    async def delete_setting(self, key: str) -> None:
        await self.execute("DELETE FROM settings WHERE key = ?", (key,))

    async def increment_stat(self, event_type: str, amount: int = 1) -> None:
        await self.execute(
            """
            INSERT INTO stats(event_type, count)
            VALUES(?, ?)
            ON CONFLICT(event_type) DO UPDATE SET
                count = count + excluded.count,
                last_updated = CURRENT_TIMESTAMP
            """,
            (event_type, amount),
        )

    async def save_ai_message(self, chat_id: int, role: str, content: str, limit: int = 50) -> None:
        row = await self.fetchone(
            "SELECT COALESCE(MAX(position), -1) AS max_pos FROM ai_memory WHERE chat_id = ?",
            (chat_id,),
        )
        position = int(row["max_pos"]) + 1
        await self.execute(
            "INSERT INTO ai_memory(chat_id, position, role, content) VALUES(?, ?, ?, ?)",
            (chat_id, position, role, content),
        )
        await self.execute(
            """
            DELETE FROM ai_memory
            WHERE chat_id = ?
              AND position < (
                  SELECT COALESCE(MAX(position), 0) - ? + 1
                  FROM ai_memory WHERE chat_id = ?
              )
            """,
            (chat_id, limit, chat_id),
        )

    async def get_ai_memory(self, chat_id: int, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            """
            SELECT role, content, created_at
            FROM ai_memory
            WHERE chat_id = ?
            ORDER BY position DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        return list(reversed(rows))

    async def replace_rotating_texts(
        self, text_type: str, texts: list[str], interval: float, active: bool
    ) -> None:
        await self.execute(
            """
            INSERT INTO rotating_texts(type, texts_json, interval, current_index, is_active)
            VALUES(?, ?, ?, 0, ?)
            ON CONFLICT(type) DO UPDATE SET
                texts_json = excluded.texts_json,
                interval = excluded.interval,
                is_active = excluded.is_active
            """,
            (text_type, json.dumps(texts, ensure_ascii=False), interval, int(active)),
        )

    async def get_rotating(self, text_type: str) -> dict[str, Any] | None:
        row = await self.fetchone(
            "SELECT * FROM rotating_texts WHERE type = ?", (text_type,)
        )
        if row:
            row["texts"] = json.loads(row.pop("texts_json"))
        return row

    async def save_error(
        self, module: str, action: str, error: str, traceback_text: str | None
    ) -> None:
        await self.execute(
            """
            INSERT INTO error_log(module, action, error, traceback)
            VALUES(?, ?, ?, ?)
            """,
            (module, action, error, traceback_text),
        )
        await self.execute(
            """
            INSERT INTO plugins(name, enabled, error_count, last_error)
            VALUES(?, 1, 1, ?)
            ON CONFLICT(name) DO UPDATE SET
                error_count = error_count + 1,
                last_error = excluded.last_error
            """,
            (module, error),
        )

    async def recent_errors(
        self, module: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        if module:
            return await self.fetchall(
                """
                SELECT * FROM error_log
                WHERE module = ?
                ORDER BY id DESC LIMIT ?
                """,
                (module, limit),
            )
        return await self.fetchall(
            "SELECT * FROM error_log ORDER BY id DESC LIMIT ?", (limit,)
        )
