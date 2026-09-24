from __future__ import annotations

from typing import Any


async def promote(client: Any, chat_id: int, user_id: int, title: str = "مدیر") -> None:
    from telethon import functions, types
    rights = types.ChatAdminRights(
        change_info=True,
        post_messages=True,
        edit_messages=True,
        delete_messages=True,
        ban_users=True,
        invite_users=True,
        pin_messages=True,
        add_admins=False,
        manage_call=True,
    )
    await client(functions.channels.EditAdminRequest(
        channel=chat_id,
        user_id=user_id,
        admin_rights=rights,
        rank=title[:16],
    ))


async def demote(client: Any, chat_id: int, user_id: int) -> None:
    from telethon import functions, types
    await client(functions.channels.EditAdminRequest(
        channel=chat_id,
        user_id=user_id,
        admin_rights=types.ChatAdminRights(),
        rank="",
    ))


async def ban(client: Any, chat_id: int, user_id: int, revoke: bool = False) -> None:
    from telethon import functions, types
    await client(functions.channels.EditBannedRequest(
        channel=chat_id,
        participant=user_id,
        banned_rights=types.ChatBannedRights(
            until_date=None,
            view_messages=True,
            send_messages=True,
            send_media=True,
        ),
    ))


async def mute(client: Any, chat_id: int, user_id: int, seconds: int) -> None:
    from telethon import functions, types
    await client(functions.channels.EditBannedRequest(
        channel=chat_id,
        participant=user_id,
        banned_rights=types.ChatBannedRights(
            until_date=seconds,
            send_messages=True,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_games=True,
            send_inline=True,
            embed_links=True,
        ),
    ))
