from __future__ import annotations

from modules.ai.gemini import GeminiChat


class ClaudeChat(GeminiChat):
    """Backward-compatible adapter name; Gemini is now the only AI backend."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
    ) -> None:
        super().__init__(api_key=api_key, model=model)
