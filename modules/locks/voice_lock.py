from __future__ import annotations


def should_block_voice(is_voice_message: bool, enabled: bool) -> bool:
    return bool(enabled and is_voice_message)
