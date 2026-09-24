from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import functions, types
from telethon.errors import FloodWaitError

from config import get_settings
from modules.accounts.manager import AccountManager
from modules.utils.database import Database


async def main() -> None:
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    manager = AccountManager(settings.api_id, settings.api_hash, settings.session_directory, db)
    try:
        await manager.connect_saved_sessions()
        client = manager.active() or next(iter(manager.clients.values()), None)
        if not client:
            raise RuntimeError("No client")

        username = "merkur_casino_spiele_onlineon"
        try:
            entity_input = await client.get_input_entity(username)
            print(f"CACHE_INPUT_OK type={type(entity_input).__name__} value={entity_input!r}")
        except Exception as exc:
            print(f"CACHE_INPUT_FAILED error={type(exc).__name__} detail={exc}")
            raise

        try:
            full = await client(functions.channels.GetFullChannelRequest(channel=entity_input))
            fc = full.full_chat
            print(
                "CACHE_FULL_OK "
                f"type={type(entity_input).__name__} "
                f"participants={getattr(fc, 'participants_count', None)}"
            )
        except FloodWaitError as exc:
            print(f"CACHE_FULL_FLOOD wait={getattr(exc, 'seconds', None)}")
            raise
    finally:
        await manager.disconnect_all()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
