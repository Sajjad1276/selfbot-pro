from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp


def search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    options = {"quiet": True, "skip_download": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(f"ytsearch{max(1, min(limit, 10))}:{query}", download=False)
    return [
        {
            "title": entry.get("title"),
            "url": entry.get("webpage_url") or entry.get("url"),
            "duration": entry.get("duration"),
        }
        for entry in data.get("entries", [])
    ]
