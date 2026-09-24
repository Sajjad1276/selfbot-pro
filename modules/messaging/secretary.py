from __future__ import annotations


def format_text(kind: str, text: str) -> str:
    tick = chr(96)
    if kind == "mono":
        return f"{tick}{text}{tick}"
    if kind == "italic":
        return f"_{text}_"
    if kind == "spoiler":
        return f"||{text}||"
    if kind == "code":
        return f"{tick}{tick}{tick}\n{text}\n{tick}{tick}{tick}"
    if kind == "quote":
        return "\n".join(f"> {line}" for line in text.splitlines())
    if kind == "strike":
        return f"~~{text}~~"
    if kind == "bold":
        return f"**{text}**"
    raise ValueError("نوع قالب‌بندی ناشناخته است.")


def supported_formats() -> tuple[str, ...]:
    return ("mono", "italic", "spoiler", "code", "quote", "strike", "bold")


async def register(client: object, db: object, settings: object, scheduler: object) -> None:
    return None
