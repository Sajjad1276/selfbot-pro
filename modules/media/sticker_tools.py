from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


def photo_to_webp(source: str, output: str, size: int = 512) -> str:
    image = Image.open(source).convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    image.save(output, "WEBP", lossless=True, method=6)
    return output


async def send_as_document(client: Any, chat_id: int, path: str) -> Any:
    return await client.send_file(chat_id, path, force_document=True)
