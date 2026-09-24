from __future__ import annotations

from google import genai
from google.genai import types


class GeminiChat:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY تنظیم نشده است.")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def reply(
        self,
        history: list[dict[str, str]],
        user_text: str,
        language: str = "fa",
    ) -> str:
        parts: list[str] = [
            "شما دستیار هوش مصنوعی SelfBot Pro هستید.",
            "پاسخ را به زبان کاربر تولید کن.",
            f"زبان ترجیحی: {language}",
        ]
        for item in history[-50:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                parts.append(f"{role}: {content}")
        parts.append(f"user: {user_text}")

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents="\n".join(parts),
            config=types.GenerateContentConfig(
                max_output_tokens=1200,
                temperature=0.7,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini پاسخی تولید نکرد.")
        return text.strip()
