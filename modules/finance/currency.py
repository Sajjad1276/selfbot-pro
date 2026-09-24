from __future__ import annotations

from decimal import Decimal
from typing import Any

import aiohttp


class CurrencyClient:
    def __init__(self, base_url: str = "https://api.frankfurter.app") -> None:
        self.base_url = base_url.rstrip("/")

    async def latest(self, base: str = "USD", symbols: list[str] | None = None) -> dict[str, Decimal]:
        params = {"from": base.upper()}
        if symbols:
            params["to"] = ",".join(x.upper() for x in symbols)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/latest", params=params, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
        return {k: Decimal(str(v)) for k, v in data.get("rates", {}).items()}

    async def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        if source.upper() == target.upper():
            return amount
        rates = await self.latest(source.upper(), [target.upper()])
        if target.upper() not in rates:
            raise ValueError("نرخ ارز در منبع فعلی موجود نیست.")
        return amount * rates[target.upper()]
