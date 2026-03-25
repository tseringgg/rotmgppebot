from __future__ import annotations

from io import BytesIO
from math import ceil
from typing import Callable, Sequence

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_quest_board(
    item_names: Sequence[str],
    image_path_resolver: Callable[[str], str | None],
    *,
    title: str = "Quest Board",
    missing_image_path: str | None = None,
    columns: int = 20,
    icon_size: int = 34,
) -> BytesIO:
    """Render a framed icon grid board for the provided items."""
    safe_columns = max(1, int(columns))
    items = list(item_names)
    rows = max(1, ceil(max(1, len(items)) / safe_columns))

    outer_pad = 24
    board_pad = 14
    slot_size = icon_size + 10
    header_height = 68
    board_width = (safe_columns * slot_size) + (board_pad * 2)
    board_height = (rows * slot_size) + (board_pad * 2)
    width = board_width + (outer_pad * 2)
    height = header_height + board_height + (outer_pad * 2)

    bg_color = (22, 22, 27, 255)
    line_color = (90, 90, 100, 255)
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(20)
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (width - title_w) // 2
    title_y = outer_pad + 4

    draw.line([(outer_pad, title_y - 2), (title_x - 18, title_y - 2)], fill=line_color, width=4)
    draw.line([(title_x + title_w + 18, title_y - 2), (width - outer_pad, title_y - 2)], fill=line_color, width=4)
    draw.text((title_x, title_y), title, font=title_font, fill=(240, 240, 245, 255))

    board_top = outer_pad + header_height
    board_left = outer_pad
    board_right = width - outer_pad
    board_bottom = board_top + board_height

    draw.rectangle([board_left, board_top, board_right, board_bottom], outline=line_color, width=3)

    fallback_icon = None
    if missing_image_path:
        try:
            fallback_icon = Image.open(missing_image_path).convert("RGBA").resize((icon_size, icon_size), Image.NEAREST)
        except OSError:
            fallback_icon = None

    for index, item in enumerate(items):
        row = index // safe_columns
        col = index % safe_columns

        x = board_left + board_pad + (col * slot_size)
        y = board_top + board_pad + (row * slot_size)

        icon = None
        resolved_path = image_path_resolver(item)
        if resolved_path:
            try:
                icon = Image.open(resolved_path).convert("RGBA")
            except OSError:
                icon = None

        if icon is None:
            icon = fallback_icon

        if icon is None:
            draw.rectangle([x, y, x + icon_size, y + icon_size], outline=(180, 70, 70, 255), width=2)
            continue

        if icon.size != (icon_size, icon_size):
            icon = icon.resize((icon_size, icon_size), Image.NEAREST)
        img.paste(icon, (x, y), icon)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer