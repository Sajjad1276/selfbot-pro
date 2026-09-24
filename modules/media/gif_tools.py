from __future__ import annotations

from pathlib import Path

from PIL import Image


def gif_to_webp(source: str, output: str, size: int = 512) -> str:
    frames = Image.open(source)
    first = frames.copy()
    first.thumbnail((size, size), Image.Resampling.LANCZOS)
    first.save(output, "WEBP", save_all=True, append_images=[], duration=frames.info.get("duration", 100), loop=0)
    return output


def webp_to_gif(source: str, output: str, duration: int = 100) -> str:
    image = Image.open(source)
    image.save(output, "GIF", save_all=True, duration=duration, loop=0)
    return output
