from __future__ import annotations

from pathlib import Path

import aiohttp


async def transcribe(
    audio_path: str,
    endpoint: str,
    api_key: str | None = None,
) -> str:
    if not endpoint:
        raise ValueError("STT_ENDPOINT تنظیم نشده است.")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    data = aiohttp.FormData()
    data.add_field(
        "file",
        Path(audio_path).read_bytes(),
        filename=Path(audio_path).name,
        content_type="application/octet-stream",
    )
    async with aiohttp.ClientSession() as session:
        async with session.post(endpoint, data=data, headers=headers, timeout=120) as response:
            response.raise_for_status()
            payload = await response.json()
    return str(payload.get("text", payload.get("transcript", ""))).strip()
