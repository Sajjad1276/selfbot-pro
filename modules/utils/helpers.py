from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import jdatetime
from rich.logging import RichHandler


PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")

T = TypeVar("T")


def to_persian_digits(value: object) -> str:
    return str(value).translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)


def jalali_now() -> jdatetime.datetime:
    return jdatetime.datetime.now()


def format_jalali(dt: datetime | None = None, with_seconds: bool = False) -> str:
    current = jdatetime.datetime.fromgregorian(datetime=dt or datetime.now())
    fmt = "%Y/%m/%d %H:%M:%S" if with_seconds else "%Y/%m/%d %H:%M"
    return to_persian_digits(current.strftime(fmt))


def rtl(text: str) -> str:
    return f"\u200f{text}\u200f"


def setup_logging(log_directory: str) -> logging.Logger:
    path = Path(log_directory)
    path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    console = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=False,
    )
    logger.addHandler(console)

    date_name = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        path / f"{date_name}.log", encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
        )
    )
    logger.addHandler(file_handler)

    return logger


def startup_banner() -> None:
    logging.getLogger("selfbot-pro").info(
        "SelfBot Pro starting | Python 3.11+ | Telethon"
    )


async def jitter_delay(low: float = 0.5, high: float = 2.0) -> None:
    await asyncio.sleep(random.uniform(low, high))


def safe_filename(name: str, default: str = "file") -> str:
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip()
    return value or default


def parse_duration(value: str) -> float:
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h|d)?\s*",
        value.lower(),
    )
    if not match:
        raise ValueError("مدت زمان نامعتبر است.")
    amount = float(match.group(1))
    unit = match.group(2) or "s"
    factor = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "d": 86400}[unit]
    return amount * factor


def split_command(text: str, prefix: str = ".") -> tuple[str, str]:
    raw = text.strip()
    if not raw.startswith(prefix):
        return "", ""
    body = raw[len(prefix):].strip()
    if not body:
        return "", ""
    parts = body.split(maxsplit=1)
    return parts[0].lower(), parts[1] if len(parts) == 2 else ""


def owner_only(owner_id: int | None, sender_id: int | None) -> bool:
    return bool(owner_id and sender_id and owner_id == sender_id)


async def guarded(
    action: Callable[[], Awaitable[T]],
    *,
    logger: logging.Logger | None = None,
    module: str = "core",
) -> T | None:
    try:
        return await action()
    except Exception:
        (logger or logging.getLogger(module)).exception("Action failed")
        return None
