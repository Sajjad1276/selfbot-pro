from __future__ import annotations

from typing import Any

import aiohttp


async def search(query: str, api_key: str, limit: int = 5) -> list[dict[str, str]]:
    if not api_key:
        raise ValueError("TENOR_API_KEY تنظیم نشده است.")
    params = {"q": query, "key": api_key, "limit": min(max(limit, 1), 20)}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://tenor.googleapis.com/v2/search", params=params, timeout=15) as response:
            response.raise_for_status()
            payload = await response.json()
    result=[]
    for item in payload.get("results", []):
        media = item.get("media_formats", {})
        gif = media.get("gif") or media.get("tinygif")
        if gif and gif.get("url"):
            result.append({"title": item.get("content_description", query), "url": gif["url"]})
    return result
