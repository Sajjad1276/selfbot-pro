from __future__ import annotations

from deep_translator import GoogleTranslator


def translate(text: str, source: str = "auto", target: str = "en") -> str:
    return GoogleTranslator(source=source, target=target).translate(text)
