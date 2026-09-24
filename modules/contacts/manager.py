from __future__ import annotations

from typing import Any


async def add_contact(client: Any, phone: str, first_name: str, last_name: str = "") -> Any:
    from telethon.tl.functions.contacts import ImportContactsRequest
    from telethon.tl.types import InputPhoneContact
    contact = InputPhoneContact(
        client_id=abs(hash(phone)) & ((1 << 63) - 1),
        phone=phone,
        first_name=first_name,
        last_name=last_name,
    )
    return await client(ImportContactsRequest([contact]))


async def delete_contact(client: Any, user_id: int) -> Any:
    from telethon.tl.functions.contacts import DeleteContactsRequest
    entity = await client.get_input_entity(user_id)
    return await client(DeleteContactsRequest(id=[entity]))


async def get_contacts(client: Any) -> list[dict[str, object]]:
    contacts = await client.get_contacts()
    return [
        {
            "id": user.id,
            "username": getattr(user, "username", None),
            "phone": getattr(user, "phone", None),
            "name": " ".join(x for x in [user.first_name, user.last_name] if x),
        }
        for user in contacts.users
    ]
