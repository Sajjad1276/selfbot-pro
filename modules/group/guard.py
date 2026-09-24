from __future__ import annotations

import re
from collections import defaultdict, deque
from time import monotonic


class GroupGuard:
    def __init__(self, banned_words: set[str] | None = None) -> None:
        self.banned_words = {w.casefold() for w in (banned_words or set()) if w}
        self._recent: dict[int, deque[tuple[int, float]]] = defaultdict(lambda: deque(maxlen=12))

    def contains_banned_word(self, text: str) -> bool:
        lowered = (text or "").casefold()
        return any(word in lowered for word in self.banned_words)

    def record(self, chat_id: int, user_id: int) -> None:
        self._recent[chat_id].append((user_id, monotonic()))

    def fight_score(self, chat_id: int, window: float = 120.0) -> int:
        cutoff = monotonic() - window
        return sum(1 for _, created in self._recent[chat_id] if created >= cutoff)

    def classify(self, text: str, chat_id: int | None = None) -> str:
        if self.contains_banned_word(text):
            return "filter"
        if chat_id is not None and self.fight_score(chat_id) >= 6:
            return "fight"
        if re.search(r"(.)\1{7,}", text or ""):
            return "noise"
        return "normal"

    def action_for(self, classification: str, sensitivity: int = 2) -> str:
        if classification == "filter":
            return "delete" if sensitivity < 4 else "warn"
        if classification == "fight":
            return "warn" if sensitivity < 4 else "mute"
        return "allow"
