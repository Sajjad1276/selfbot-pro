from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp


def download(url: str, output_dir: str, quality: str = "720", audio_only: bool = False) -> str:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    height = int(quality) if quality.isdigit() else 720
    ydl_opts: dict[str, Any] = {
        "outtmpl": str(path / "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if audio_only:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best[height<={height}]/best"
        ydl_opts["merge_output_format"] = "mp4"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    if audio_only:
        return str(Path(filename).with_suffix(".mp3"))
    return filename
