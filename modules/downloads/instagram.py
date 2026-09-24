from __future__ import annotations

from pathlib import Path

import yt_dlp


def download(url: str, output_dir: str) -> str:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(path / "%(uploader).40s-%(title).60s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)
