from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from dataclass import Loot, PPEData, PlayerData
from utils.points_service import (
    apply_percent_modifier,
    calculate_item_points,
    get_effective_modifier_bucket_for_ppe,
    loot_adjustments_for_ppe,
)
from utils.season_loot_history import iter_season_variants


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_gradient_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    top = (12, 27, 46)
    bottom = (20, 44, 74)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _format_tick(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _format_date(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%m-%d")


def _draw_line_chart(
    *,
    title: str,
    subtitle: str,
    x_values: list[int],
    y_values: list[float],
    x_axis_label: str,
    y_axis_label: str,
) -> BytesIO:
    width, height = 1240, 760
    img = Image.new("RGB", (width, height), (18, 32, 52))
    draw = ImageDraw.Draw(img)
    _draw_gradient_background(draw, width, height)

    title_font = _load_font(42, bold=True)
    subtitle_font = _load_font(24)
    label_font = _load_font(20, bold=True)
    tick_font = _load_font(18)

    chart_left = 120
    chart_top = 150
    chart_right = width - 70
    chart_bottom = height - 120

    draw.rounded_rectangle(
        [(40, 40), (width - 40, height - 40)],
        radius=24,
        outline=(117, 201, 255),
        width=3,
        fill=(17, 36, 60),
    )

    draw.text((70, 66), title, fill=(238, 248, 255), font=title_font)
    draw.text((70, 113), subtitle, fill=(173, 210, 237), font=subtitle_font)

    y_min_raw = min(y_values)
    y_max_raw = max(y_values)
    if y_max_raw == y_min_raw:
        y_padding = max(1.0, abs(y_max_raw) * 0.2)
        y_min = y_min_raw - y_padding
        y_max = y_max_raw + y_padding
    else:
        y_padding = (y_max_raw - y_min_raw) * 0.12
        y_min = y_min_raw - y_padding
        y_max = y_max_raw + y_padding

    if y_min > 0:
        y_min = 0.0

    x_min = min(x_values)
    x_max = max(x_values)

    for i in range(6):
        t = i / 5
        y = chart_bottom - int((chart_bottom - chart_top) * t)
        value = y_min + (y_max - y_min) * t
        draw.line([(chart_left, y), (chart_right, y)], fill=(52, 88, 122), width=1)
        draw.text((26, y - 10), _format_tick(value), fill=(188, 217, 240), font=tick_font)

    for i in range(6):
        t = i / 5
        x = chart_left + int((chart_right - chart_left) * t)
        draw.line([(x, chart_top), (x, chart_bottom)], fill=(40, 70, 100), width=1)
        ts_value = int(x_min + (x_max - x_min) * t)
        draw.text((x - 24, chart_bottom + 12), _format_date(ts_value), fill=(188, 217, 240), font=tick_font)

    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=(214, 236, 255), width=2)
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=(214, 236, 255), width=2)
    draw.text((chart_right - 110, chart_bottom + 46), x_axis_label, fill=(214, 236, 255), font=label_font)
    draw.text((24, chart_top - 36), y_axis_label, fill=(214, 236, 255), font=label_font)

    def map_x(raw_ts: int) -> int:
        if x_max == x_min:
            return (chart_left + chart_right) // 2
        return chart_left + int((raw_ts - x_min) / (x_max - x_min) * (chart_right - chart_left))

    def map_y(raw_value: float) -> int:
        if y_max == y_min:
            return (chart_top + chart_bottom) // 2
        return chart_bottom - int((raw_value - y_min) / (y_max - y_min) * (chart_bottom - chart_top))

    points = [(map_x(ts), map_y(value)) for ts, value in zip(x_values, y_values)]
    if len(points) >= 2:
        draw.line(points, fill=(255, 210, 99), width=4, joint="curve")

    for point in points:
        x, y = point
        draw.ellipse([(x - 4, y - 4), (x + 4, y + 4)], fill=(255, 248, 236), outline=(255, 210, 99), width=2)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _loot_drop_event_timestamps(loot: Loot) -> list[int]:
    raw_times = getattr(loot, "logged_times", [])
    if isinstance(raw_times, list) and raw_times:
        parsed: list[int] = []
        for raw_ts in raw_times:
            try:
                ts = int(raw_ts)
            except (TypeError, ValueError):
                continue
            if ts > 0:
                parsed.append(ts)
        parsed.sort()
        if parsed:
            return parsed
    return []


def _drop_points_for_single_event(loot: Loot, ppe: PPEData, guild_config: dict | None) -> float:
    base = calculate_item_points(
        item_name=str(loot.item_name),
        divine=bool(loot.divine),
        shiny=bool(loot.shiny),
        quantity=1,
        rarity=str(getattr(loot, "rarity", "common")),
        guild_config=guild_config,
    )
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    adjustments = loot_adjustments_for_ppe(ppe, guild_config)

    adjusted = apply_percent_modifier(base, float(modifier_bucket.get("loot_percent", 0.0) or 0.0))
    adjusted = apply_percent_modifier(adjusted, float(modifier_bucket.get("total_percent", 0.0) or 0.0))
    adjusted *= float(adjustments.get("reduction_multiplier", 1.0) or 1.0)
    adjusted *= float(adjustments.get("type_multiplier", 1.0) or 1.0)
    return float(adjusted)


def build_item_graph(player_data: PlayerData, *, display_name: str) -> BytesIO | None:
    variant_rows = iter_season_variants(player_data)
    if not variant_rows:
        return None

    events: list[int] = []
    for _item_name, _shiny, _rarity, timestamps in variant_rows:
        events.extend(int(ts) for ts in timestamps if int(ts) > 0)

    events.sort()
    if not events:
        return None

    x_values: list[int] = []
    y_values: list[float] = []
    total = 0
    for ts in events:
        total += 1
        x_values.append(ts)
        y_values.append(float(total))

    subtitle = (
        f"{len(variant_rows)} variants tracked, {total} total pickups, "
        f"{_format_date(events[0])} → {_format_date(events[-1])}"
    )
    return _draw_line_chart(
        title=f"{display_name} - Season Item Graph",
        subtitle=subtitle,
        x_values=x_values,
        y_values=y_values,
        x_axis_label="Date (UTC)",
        y_axis_label="Total Items",
    )


def build_character_point_graph(
    ppe: PPEData,
    *,
    display_name: str,
    guild_config: dict | None,
) -> BytesIO | None:
    events: list[tuple[int, float]] = []
    total_loot_points = 0.0

    for loot in list(getattr(ppe, "loot", [])):
        event_times = _loot_drop_event_timestamps(loot)
        if not event_times:
            continue

        points_per_event = _drop_points_for_single_event(loot, ppe, guild_config)
        for ts in event_times:
            events.append((ts, points_per_event))
            total_loot_points += points_per_event

    if not events:
        return None

    events.sort(key=lambda row: row[0])
    baseline = float(getattr(ppe, "points", 0.0) or 0.0) - float(total_loot_points)

    x_values: list[int] = []
    y_values: list[float] = []
    cumulative = baseline
    for ts, delta in events:
        cumulative += float(delta)
        x_values.append(int(ts))
        y_values.append(float(cumulative))

    subtitle = f"PPE #{ppe.id} point progression from logged drops ({_format_date(x_values[0])} → {_format_date(x_values[-1])})"
    return _draw_line_chart(
        title=f"{display_name} - PPE #{ppe.id} Point Graph",
        subtitle=subtitle,
        x_values=x_values,
        y_values=y_values,
        x_axis_label="Date (UTC)",
        y_axis_label="Points",
    )
