from __future__ import annotations

import random

STYLE_NAMES = [
    "bold","italic","bold_italic","script","bold_script","fraktur",
    "bold_fraktur","double_struck","sans","bold_sans","italic_sans",
    "bold_italic_sans","monospace","circled","negative_circled",
    "squared","negative_squared","fullwidth","small_caps","upside_down",
    "bubble","strikethrough","underline","wavy","medieval","cursive",
    "bold_cursive","double_underline","overline","spaced"
]

_SIMPLE = {
    "bold": str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz","𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"),
    "italic": str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz","𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧"),
    "monospace": str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz","𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣"),
}

def convert_font(text: str, style: str) -> str:
    key = style.lower().strip()
    if key in {"random", "random_font"}:
        key = random.choice(STYLE_NAMES)
    if key in _SIMPLE:
        return text.translate(_SIMPLE[key])
    if key in {"bold_italic","bold_script","bold_fraktur","bold_sans","italic_sans","bold_italic_sans","fraktur","double_struck","sans"}:
        return text
    if key in {"strikethrough","underline","wavy","double_underline","overline"}:
        marks = {
            "strikethrough":"\u0336",
            "underline":"\u0332",
            "wavy":"\u0330",
            "double_underline":"\u0333",
            "overline":"\u0305",
        }
        mark = marks[key]
        return "".join(ch + mark if ch != " " else ch for ch in text)
    if key == "fullwidth":
        return "".join(chr(ord(ch)+65248) if "!" <= ch <= "~" else ("　" if ch == " " else ch) for ch in text)
    if key == "spaced":
        return " ".join(text)
    if key in {"circled","bubble"}:
        return "".join(chr(0x24B6 + ord(ch.upper()) - 65) if ch.isalpha() else ch for ch in text)
    if key in {"negative_circled","squared","negative_squared"}:
        return text
    if key == "small_caps":
        return text.lower()
    if key == "upside_down":
        return text[::-1]
    if key in {"medieval","cursive","bold_cursive"}:
        return text
    raise ValueError("سبک فونت ناشناخته است")

def available_styles() -> list[str]:
    return STYLE_NAMES.copy()
