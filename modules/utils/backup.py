from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


async def export_settings(db: Any, output: str) -> str:
    rows = await db.fetchall("SELECT key, value FROM settings ORDER BY key")
    payload = {row["key"]: row["value"] for row in rows}
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


async def import_settings(db: Any, source: str) -> int:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("فایل پشتیبان معتبر نیست.")
    for key, value in payload.items():
        await db.set_setting(str(key), str(value))
    return len(payload)


async def backup_database(db_path: str, output: str) -> str:
    source = Path(db_path)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    await __import__("asyncio").to_thread(shutil.copy2, source, destination)
    return str(destination)
