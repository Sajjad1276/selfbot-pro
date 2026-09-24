from __future__ import annotations

from typing import Any

import anthropic


class ClaudeChat:
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def reply(self, history: list[dict[str, str]], user_text: str) -> str:
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history
            if item["role"] in {"user", "assistant"}
        ]
        messages.append({"role": "user", "content": user_text})
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system="به زبان کاربر پاسخ بده. پاسخ روشن، دقیق و کوتاه باشد.",
            messages=messages,
        )
        blocks = getattr(response, "content", [])
        return "".join(getattr(block, "text", "") for block in blocks).strip()
