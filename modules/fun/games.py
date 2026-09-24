from __future__ import annotations

import random


def dice(sides: int = 6) -> int:
    return random.SystemRandom().randint(1, max(2, min(sides, 100)))


def bowling() -> int:
    return random.SystemRandom().randint(0, 6)


def basketball() -> int:
    return random.SystemRandom().randint(1, 5)


def penalty() -> int:
    return random.SystemRandom().randint(1, 5)
