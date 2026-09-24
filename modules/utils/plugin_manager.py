from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Any


class PluginManager:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.loaded: dict[str, ModuleType] = {}
        self.logger = logging.getLogger("selfbot.plugins")

    async def load(self, name: str) -> ModuleType:
        module = importlib.import_module(name)
        self.loaded[name] = module
        await self.db.execute(
            """
            INSERT INTO plugins(name, enabled, loaded_at)
            VALUES(?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                enabled = 1,
                loaded_at = CURRENT_TIMESTAMP
            """,
            (name,),
        )
        return module

    async def unload(self, name: str) -> bool:
        if name not in self.loaded:
            await self.db.execute(
                "UPDATE plugins SET enabled = 0 WHERE name = ?", (name,)
            )
            return False
        self.loaded.pop(name, None)
        await self.db.execute(
            "UPDATE plugins SET enabled = 0 WHERE name = ?", (name,)
        )
        return True

    async def list_plugins(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT name, enabled, loaded_at, error_count, last_error FROM plugins ORDER BY name"
        )

    def get(self, name: str) -> ModuleType | None:
        return self.loaded.get(name)
