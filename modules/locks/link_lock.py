from __future__ import annotations

import re

URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)


def contains_link(text: str) -> bool:
    return bool(URL_RE.search(text or ""))
