from __future__ import annotations

FRIEND_TEMPLATES = [
    "سلام، خوش آمدی.",
    "پیامت رسید.",
    "در خدمتم.",
    "ممنون که پیام دادی.",
    "الان در دسترسم.",
    "پیامت را دیدم.",
]

ENEMY_TEMPLATES = [
    "فعلاً پاسخی ندارم.",
    "بعداً بررسی می‌کنم.",
    "در حال حاضر پاسخ نمی‌دهم.",
    "پیام دریافت شد.",
    "زمان مناسب نیست.",
    "فعلاً مزاحم نشو.",
]

MIXED_TEMPLATES = [
    "پیامت دریافت شد.",
    "بررسی می‌کنم.",
    "الان فرصت کوتاه است.",
    "بعداً ادامه می‌دهیم.",
    "ممنون.",
    "باشه.",
]


def _expand(templates: list[str], count: int) -> list[str]:
    result: list[str] = []
    i = 0
    while len(result) < count:
        base = templates[i % len(templates)]
        cycle = i // len(templates)
        result.append(base if cycle == 0 else f"{base} ({cycle + 1})")
        i += 1
    return result[:count]


def friend_responses(count: int = 200) -> list[str]:
    return _expand(FRIEND_TEMPLATES, count)


def enemy_responses(count: int = 400) -> list[str]:
    return _expand(ENEMY_TEMPLATES, count)


def mixed_responses(count: int = 120) -> list[str]:
    return _expand(MIXED_TEMPLATES, count)
