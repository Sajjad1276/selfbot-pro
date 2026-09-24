from __future__ import annotations

import hashlib

SIGNS = {
    "حمل": "aries", "ثور": "taurus", "جوزا": "gemini", "سرطان": "cancer",
    "اسد": "leo", "سنبله": "virgo", "میزان": "libra", "عقرب": "scorpio",
    "قوس": "sagittarius", "جدی": "capricorn", "دلو": "aquarius", "حوت": "pisces",
}

TEXTS = [
    "امروز روی کارهای کوچک و قابل کنترل تمرکز کن.",
    "یک تصمیم روشن از چند تصمیم عجولانه بهتر است.",
    "زمان را برای کار اصلی نگه دار و حواس‌پرتی را کم کن.",
    "گفت‌وگوی دقیق از حدس زدن نتیجه بهتری می‌دهد.",
]


def daily(sign: str, date: str) -> str:
    key = SIGNS.get(sign, sign).encode()
    index = int(hashlib.sha256(key + date.encode()).hexdigest(), 16) % len(TEXTS)
    return TEXTS[index]
