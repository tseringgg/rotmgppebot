from __future__ import annotations

import os
from io import BytesIO
from math import ceil
from typing import Callable, Sequence

from PIL import Image, ImageDraw, ImageFont


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Prefer local pixel fonts, then scalable system fallbacks.
    for candidate in (        
        os.path.join(_THIS_DIR, "pixel_font.ttf"),
        os.path.join(_THIS_DIR, "PressStart2P.ttf"),
        "DejaVuSansMono-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue

    # Last resort bitmap fallback (fixed-size appearance).
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
    
    # --- Grid Math ---
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

    # --- Sizing Base Variables ---
    pad = 20
    slot_size = icon_size + 12
    
    grid_width = (safe_columns * slot_size)
    grid_height = (rows * slot_size)
    
    # --- Measure Text & Calculate Responsive Width ---
    # Use a large but practical default title size.
    title_font = _load_font(18)
    
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    title_bbox = dummy_draw.textbbox((0, 0), title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]

    # Smart Width: Box will fit the grid, UNLESS the title is wider.
    # We add 80px of padding to ensure the text never touches the walls.
    width = max(grid_width + 80, title_w + 80)

    # Calculate exact vertical placements
    title_y = pad + 16
    div_y = title_y + title_h + 20
    board_top = div_y + 24
    
    # Snug height calculation
    height = board_top + grid_height + 24 

    # --- Colors ---
    bg_color = (25, 25, 25, 255)       
    frame_color = (100, 100, 100, 255) 
    title_color = (255, 255, 255, 255) 

    # Create the actual image
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # --- Draw Thicker Custom Retro Frame ---
    line_w = 4 
    c_len = 24 
    c_gap = 12 
    
    # 1. Outer Box Lines
    draw.line([(pad + c_len + c_gap, pad), (width - pad - c_len - c_gap, pad)], fill=frame_color, width=line_w)
    draw.line([(pad + c_len + c_gap, height - pad), (width - pad - c_len - c_gap, height - pad)], fill=frame_color, width=line_w)
    draw.line([(pad, pad + c_len + c_gap), (pad, height - pad - c_len - c_gap)], fill=frame_color, width=line_w)
    draw.line([(width - pad, pad + c_len + c_gap), (width - pad, height - pad - c_len - c_gap)], fill=frame_color, width=line_w)

    # 2. Corner Brackets & Inner Dots
    corners = [
        ([(pad, pad + c_len), (pad, pad), (pad + c_len, pad)], (pad + 8, pad + 8)),
        ([(width - pad - c_len, pad), (width - pad, pad), (width - pad, pad + c_len)], (width - pad - 12, pad + 8)),
        ([(pad, height - pad - c_len), (pad, height - pad), (pad + c_len, height - pad)], (pad + 8, height - pad - 12)),
        ([(width - pad - c_len, height - pad), (width - pad, height - pad), (width - pad, height - pad - c_len)], (width - pad - 12, height - pad - 12))
    ]
    
    for lines, dot in corners:
        draw.line(lines, fill=frame_color, width=line_w)
        draw.rectangle([dot[0], dot[1], dot[0] + 3, dot[1] + 3], fill=frame_color)

    # --- Draw Text & Horizontal Separator ---
    title_x = (width - title_w) // 2
    
    # Clean, larger text with no artificial bold stroke
    draw.text(
        (title_x, title_y), 
        title, 
        font=title_font, 
        fill=title_color
    )

    # Horizontal divider below text
    div_pad = pad + 16
    draw.line([(div_pad + 16, div_y), (width - div_pad - 16, div_y)], fill=frame_color, width=line_w)
    
    # Separator endpoints
    draw.rectangle([(div_pad, div_y - 2), (div_pad + 3, div_y + 1)], fill=frame_color)
    draw.rectangle([(width - div_pad - 4, div_y - 2), (width - div_pad - 1, div_y + 1)], fill=frame_color)

    # --- Draw Grid Items ---
    # Center the entire grid block relative to the dynamic width
    board_left = (width - grid_width) // 2

    fallback_icon = None
    if missing_image_path:
        try:
            fallback_icon = Image.open(missing_image_path).convert("RGBA").resize((icon_size, icon_size), Image.NEAREST)
        except OSError:
            fallback_icon = None

    for index, item in enumerate(items):
        row = index // safe_columns
        col = index % safe_columns

        x = board_left + (col * slot_size) + (slot_size - icon_size) // 2
        y = board_top + (row * slot_size)

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

    # --- Output ---
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer