from __future__ import annotations

from pathlib import Path

from gtts import gTTS


def synthesize(text: str, output_path: str, lang: str = "fa") -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    gTTS(text=text, lang=lang).save(str(path))
    return str(path)
