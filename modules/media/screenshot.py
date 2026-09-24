from __future__ import annotations

from pathlib import Path
from typing import Any


async def download_reply_media(client: Any, message: Any, output_dir: str) -> str | None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return await client.download_media(message, file=str(path))
