from __future__ import annotations


def should_block_media(has_media: bool, enabled: bool, media_kind: str = "") -> bool:
    if not enabled or not has_media:
        return False
    return media_kind.lower() in {"photo", "video", "document", "gif"}
