from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def make_logo(
    text: str,
    output: str,
    width: int = 800,
    height: int = 400,
    background: tuple[int, int, int, int] = (18, 18, 18, 255),
) -> str:
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    x = (width - (box[2] - box[0])) // 2
    y = (height - (box[3] - box[1])) // 2
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    image.save(output, "PNG")
    return output
