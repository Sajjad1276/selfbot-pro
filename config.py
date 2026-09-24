from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"متغیر محیطی {name} تنظیم نشده است.")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str
    owner_id: int | None
    anthropic_api_key: str | None
    log_channel: int | str | None
    timezone: str
    default_lang: str
    database_path: str
    session_directory: str
    log_directory: str
    prefix: str
    http_host: str
    http_port: int


def get_settings() -> Settings:
    api_id = int(_required("API_ID"))
    api_hash = _required("API_HASH")
    phone = os.getenv("PHONE", "").strip()
    owner_raw = os.getenv("OWNER_ID", "").strip()
    log_channel_raw = os.getenv("LOG_CHANNEL", "").strip()

    if owner_raw and not owner_raw.lstrip("-").isdigit():
        raise RuntimeError("OWNER_ID باید عدد باشد.")

    if log_channel_raw and log_channel_raw.lstrip("-").isdigit():
        log_channel: int | str | None = int(log_channel_raw)
    else:
        log_channel = log_channel_raw or None

    database_path = os.getenv(
        "DATABASE_PATH", str(ROOT / "data" / "selfbot.db")
    )

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        owner_id=int(owner_raw) if owner_raw else None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        log_channel=log_channel,
        timezone=os.getenv("TIMEZONE", "Asia/Tehran"),
        default_lang=os.getenv("DEFAULT_LANG", "fa"),
        database_path=database_path,
        session_directory=os.getenv(
            "SESSION_DIRECTORY", str(ROOT / "sessions")
        ),
        log_directory=os.getenv("LOG_DIRECTORY", str(ROOT / "logs")),
        prefix=os.getenv("BOT_PREFIX", ".") or ".",
        http_host=os.getenv("HTTP_HOST", "127.0.0.1"),
        http_port=int(os.getenv("HTTP_PORT", "8080")),
    )


@property
def session_path_placeholder() -> str:
    return ""
