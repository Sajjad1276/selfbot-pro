from __future__ import annotations

from typing import Any


async def search_contacts(client: Any, query: str) -> list[dict[str, object]]:
    query = query.strip().casefold()
    if not query:
        return []

    contacts = await client.get_contacts()
    matches: list[dict[str, object]] = []

    for user in contacts.users:
        first = getattr(user, "first_name", None) or ""
        last = getattr(user, "last_name", None) or ""
        username = getattr(user, "username", None) or ""
        name = " ".join(x for x in (first, last) if x).strip()
        candidates = (name, username, f"{first} {last}".strip())
        if any(query in value.casefold() for value in candidates if value):
            matches.append({
                "id": user.id,
                "name": name,
                "username": username or None,
            })

    return matches
