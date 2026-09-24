from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    load_dotenv()
    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]
    phone = os.environ.get("PHONE") or input("Phone: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start(phone=phone)
    session = client.session.save()
    print("\nSTRING_SESSION=")
    print(session)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
