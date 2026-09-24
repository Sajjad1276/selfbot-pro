from __future__ import annotations

from typing import Iterable


def should_allow_private_message(sender_id: int, contact_ids: Iterable[int], enabled: bool) -> bool:
    if not enabled:
        return True
    return sender_id in set(contact_ids)
