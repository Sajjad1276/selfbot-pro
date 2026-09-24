from __future__ import annotations

from collections import deque
from typing import Any


class MessageArchive:
    def __init__(self, per_chat: int = 200) -> None:
        self.messages: dict[int, deque[dict[str, object]]] = {}
        self.per_chat = per_chat

    def remember(self, message: Any) -> None:
        chat_id = int(message.chat_id)
        queue = self.messages.setdefault(chat_id, deque(maxlen=self.per_chat))
        queue.append({
            "id": message.id,
            "sender_id": message.sender_id,
            "text": message.raw_text or "",
            "date": message.date.isoformat() if message.date else None,
        })

    def mark_deleted(self, chat_id: int, message_ids: list[int]) -> list[dict[str, object]]:
        queue = self.messages.get(chat_id, ())
        wanted = set(message_ids)
        return [item for item in queue if item["id"] in wanted]


def register_cache(client: Any, archive: MessageArchive) -> None:
    from telethon import events

    @client.on(events.NewMessage())
    async def cache_message(event: Any) -> None:
        archive.remember(event.message)
