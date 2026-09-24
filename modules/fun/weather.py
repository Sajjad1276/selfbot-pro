from __future__ import annotations

from typing import Any

import aiohttp


async def get_weather(city: str) -> dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
            headers={"User-Agent": "SelfBot-Pro/1.0"},
            timeout=15,
        ) as response:
            response.raise_for_status()
            data = await response.json()
    current = data["current_condition"][0]
    return {
        "city": city,
        "temperature_c": current.get("temp_C"),
        "feels_like_c": current.get("FeelsLikeC"),
        "description": current.get("weatherDesc", [{}])[0].get("value"),
        "humidity": current.get("humidity"),
        "wind_kmh": current.get("windspeedKmph"),
    }
