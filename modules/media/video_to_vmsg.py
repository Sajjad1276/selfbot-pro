from __future__ import annotations

import asyncio
from pathlib import Path

import ffmpeg


async def video_to_round(source: str, output: str) -> str:
    source_path = Path(source)
    stream = ffmpeg.input(str(source_path))
    stream = stream.output(
        str(output),
        vf="crop=min(iw\,ih):min(iw\,ih),scale=480:480",
        vcodec="libx264",
        acodec="aac",
        movflags="+faststart",
        t=60,
    )
    await asyncio.to_thread(ffmpeg.run, stream, overwrite_output=True, quiet=True)
    return str(output)
