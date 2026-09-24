from __future__ import annotations

import random

from .responses import enemy_responses, friend_responses, mixed_responses


VALID_TYPES = {"friend", "enemy", "neutral"}


async def set_status(db: object, user_id: int, status: str) -> None:
    if status not in VALID_TYPES:
        raise ValueError("نوع وضعیت کاربر نامعتبر است.")
    await db.execute(
        """
        INSERT INTO friends(user_id, type)
        VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET type=excluded.type
        """,
        (user_id, status),
    )


async def remove_status(db: object, user_id: int) -> None:
    await db.execute("DELETE FROM friends WHERE user_id=?", (user_id,))


async def get_status(db: object, user_id: int) -> str:
    row = await db.fetchone("SELECT type FROM friends WHERE user_id=?", (user_id,))
    return row["type"] if row else "neutral"


def choose_response(status: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    pools = {
        "friend": friend_responses(),
        "enemy": enemy_responses(),
        "neutral": mixed_responses(),
    }
    return rng.choice(pools.get(status, pools["neutral"]))
