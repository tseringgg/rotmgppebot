from __future__ import annotations

from io import BytesIO
from math import ceil
from typing import Callable, Sequence

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "DejaVuSansMono-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "arial.ttf",
    ):
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
    columns: int | None = None,
    icon_size: int = 34,
) -> BytesIO:
    """Render a framed icon grid board for the provided items."""
    items = list(item_names)
    if columns is None or int(columns) <= 0:
        count = max(1, len(items))
        if count <= 8:
            safe_columns = count
        elif count <= 24:
            safe_columns = 8
        elif count <= 48:
            safe_columns = 10
        else:
            safe_columns = 12
    else:
        safe_columns = max(1, int(columns))

    rows = max(1, ceil(max(1, len(items)) / safe_columns))

    outer_pad = 26
    panel_pad = 18
    grid_pad = 16
    slot_size = icon_size + 11
    title_gap = 84
    grid_width = (safe_columns * slot_size) + (grid_pad * 2)
    grid_height = (rows * slot_size) + (grid_pad * 2)
    panel_width = grid_width + (panel_pad * 2)
    panel_height = title_gap + grid_height + panel_pad
    width = panel_width + (outer_pad * 2)
    height = panel_height + (outer_pad * 2)

    bg_color = (21, 21, 25, 255)
    panel_color = (27, 27, 33, 255)
    frame_color = (76, 79, 92, 255)
    title_color = (243, 243, 246, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    panel_left = outer_pad
    panel_top = outer_pad
    panel_right = panel_left + panel_width
    panel_bottom = panel_top + panel_height

    draw.rectangle([panel_left, panel_top, panel_right, panel_bottom], fill=panel_color)
    draw.rectangle([panel_left, panel_top, panel_right, panel_bottom], outline=frame_color, width=3)

    title_font = _load_font(64 if width > 1500 else 50 if width > 1100 else 40)
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    min_panel_for_title = title_w + 180
    if panel_width < min_panel_for_title:
        panel_width = min_panel_for_title
        width = panel_width + (outer_pad * 2)
        img = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        panel_left = outer_pad
        panel_top = outer_pad
        panel_right = panel_left + panel_width
        panel_bottom = panel_top + panel_height
        draw.rectangle([panel_left, panel_top, panel_right, panel_bottom], fill=panel_color)
        draw.rectangle([panel_left, panel_top, panel_right, panel_bottom], outline=frame_color, width=3)

    title_x = panel_left + (panel_width - title_w) // 2
    title_y = panel_top + 18

    title_box_left = panel_left + 24
    title_box_top = panel_top + 12
    title_box_right = panel_right - 24
    title_box_bottom = panel_top + title_gap - 20
    draw.rectangle([title_box_left, title_box_top, title_box_right, title_box_bottom], outline=frame_color, width=3)

    left_sep_start = title_box_left + 18
    left_sep_end = title_x - 24
    right_sep_start = title_x + title_w + 24
    right_sep_end = title_box_right - 18
    sep_y = title_y + (title_h // 2)
    if left_sep_end > left_sep_start:
        draw.line([(left_sep_start, sep_y), (left_sep_end, sep_y)], fill=frame_color, width=6)
    if right_sep_end > right_sep_start:
        draw.line([(right_sep_start, sep_y), (right_sep_end, sep_y)], fill=frame_color, width=6)
    draw.text(
        (title_x, title_y),
        title,
        font=title_font,
        fill=title_color,
        stroke_width=2,
        stroke_fill=(12, 12, 15, 255),
    )

    divider_y = panel_top + title_gap - 12
    draw.line([(panel_left + 18, divider_y), (panel_right - 18, divider_y)], fill=frame_color, width=4)

    board_left = panel_left + (panel_width - grid_width) // 2
    board_top = panel_top + title_gap
    board_right = board_left + grid_width
    board_bottom = board_top + grid_height

    draw.rectangle([board_left, board_top, board_right, board_bottom], outline=frame_color, width=3)

    corner_len = 24
    corner_width = 3
    corner_points = [
        ((panel_left + 10, panel_top + 10), (panel_left + 10 + corner_len, panel_top + 10), (panel_left + 10, panel_top + 10 + corner_len)),
        ((panel_right - 10, panel_top + 10), (panel_right - 10 - corner_len, panel_top + 10), (panel_right - 10, panel_top + 10 + corner_len)),
        ((panel_left + 10, panel_bottom - 10), (panel_left + 10 + corner_len, panel_bottom - 10), (panel_left + 10, panel_bottom - 10 - corner_len)),
        ((panel_right - 10, panel_bottom - 10), (panel_right - 10 - corner_len, panel_bottom - 10), (panel_right - 10, panel_bottom - 10 - corner_len)),
    ]
    for anchor, horizontal_end, vertical_end in corner_points:
        draw.line([anchor, horizontal_end], fill=frame_color, width=corner_width)
        draw.line([anchor, vertical_end], fill=frame_color, width=corner_width)

    fallback_icon = None
    if missing_image_path:
        try:
            fallback_icon = Image.open(missing_image_path).convert("RGBA").resize((icon_size, icon_size), Image.NEAREST)
        except OSError:
            fallback_icon = None

    for index, item in enumerate(items):
        row = index // safe_columns
        col = index % safe_columns

        x = board_left + grid_pad + (col * slot_size)
        y = board_top + grid_pad + (row * slot_size)

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