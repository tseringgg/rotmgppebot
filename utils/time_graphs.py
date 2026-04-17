"""Utilities for time graphs."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import math
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from dataclass import Loot, PPEData, PlayerData
from utils.points_service import (
    apply_percent_modifier,
    calculate_item_points,
    get_effective_modifier_bucket_for_ppe,
    loot_adjustments_for_ppe,
)
from utils.loot_constants import normalize_rarity
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


def _format_time_tick(ts: int, span_seconds: int) -> str:
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    if span_seconds <= 6 * 3600:
        return dt.strftime("%H:%M")
    if span_seconds <= 2 * 24 * 3600:
        return dt.strftime("%m-%d %H:%M")
    if span_seconds <= 180 * 24 * 3600:
        return dt.strftime("%m-%d")
    if span_seconds <= 2 * 365 * 24 * 3600:
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y")


def _build_time_ticks(x_min: int, x_max: int, *, max_labels: int) -> list[int]:
    if x_max <= x_min:
        return [x_min]

    span = x_max - x_min
    target_step = span / max(1, max_labels - 1)
    candidate_steps = [
        60,
        5 * 60,
        10 * 60,
        15 * 60,
        30 * 60,
        60 * 60,
        2 * 60 * 60,
        3 * 60 * 60,
        6 * 60 * 60,
        12 * 60 * 60,
        24 * 60 * 60,
        2 * 24 * 60 * 60,
        3 * 24 * 60 * 60,
        7 * 24 * 60 * 60,
        14 * 24 * 60 * 60,
        30 * 24 * 60 * 60,
        90 * 24 * 60 * 60,
        180 * 24 * 60 * 60,
        365 * 24 * 60 * 60,
    ]
    step = next((s for s in candidate_steps if s >= target_step), candidate_steps[-1])

    ticks = [x_min]
    first_aligned = ((x_min // step) + 1) * step
    current = first_aligned
    while current < x_max:
        ticks.append(current)
        current += step
    if ticks[-1] != x_max:
        ticks.append(x_max)

    deduped: list[int] = []
    for tick in ticks:
        if not deduped or deduped[-1] != tick:
            deduped.append(tick)
    return deduped


def _build_integer_ticks(y_min_raw: float, y_max_raw: float) -> list[int]:
    y_min_int = int(math.floor(y_min_raw))
    y_max_int = int(math.ceil(y_max_raw))
    if y_min_int > 0:
        y_min_int = 0
    if y_max_int <= y_min_int:
        y_max_int = y_min_int + 1

    span = y_max_int - y_min_int
    target_count = 6
    step = max(1, int(math.ceil(span / max(1, target_count - 1))))

    ticks = list(range(y_min_int, y_max_int + 1, step))
    if ticks[-1] != y_max_int:
        ticks.append(y_max_int)
    return ticks


def _append_current_time_point(x_values: list[int], y_values: list[float]) -> None:
    if not x_values or not y_values:
        return

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if now_ts > int(x_values[-1]):
        x_values.append(now_ts)
        y_values.append(float(y_values[-1]))


def _draw_line_chart(
    *,
    title: str,
    subtitle: str,
    x_values: list[int],
    y_values: list[float],
    x_axis_label: str,
    y_axis_label: str,
    y_axis_integers: bool = False,
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
    y_ticks: list[float]
    if y_axis_integers:
        int_ticks = _build_integer_ticks(y_min_raw, y_max_raw)
        y_ticks = [float(tick) for tick in int_ticks]
        y_min = y_ticks[0]
        y_max = y_ticks[-1]
    else:
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
        y_ticks = [y_min + (y_max - y_min) * (i / 5) for i in range(6)]

    x_min = min(x_values)
    x_max = max(x_values)

    for value in y_ticks:
        if y_max == y_min:
            y = (chart_top + chart_bottom) // 2
        else:
            y = chart_bottom - int((value - y_min) / (y_max - y_min) * (chart_bottom - chart_top))
        draw.line([(chart_left, y), (chart_right, y)], fill=(52, 88, 122), width=1)
        tick_label = str(int(value)) if y_axis_integers else _format_tick(value)
        tick_box = draw.textbbox((0, 0), tick_label, font=tick_font)
        tick_w = tick_box[2] - tick_box[0]
        tick_h = tick_box[3] - tick_box[1]
        draw.text((chart_left - 12 - tick_w, y - tick_h // 2), tick_label, fill=(188, 217, 240), font=tick_font)

    span_seconds = max(0, x_max - x_min)
    max_x_labels = max(3, min(8, (chart_right - chart_left) // 140))
    x_ticks = _build_time_ticks(x_min, x_max, max_labels=max_x_labels)
    x_label_candidates: list[tuple[int, str, int, int]] = []
    for ts_value in x_ticks:
        if x_max == x_min:
            x = (chart_left + chart_right) // 2
        else:
            x = chart_left + int((ts_value - x_min) / (x_max - x_min) * (chart_right - chart_left))
        draw.line([(x, chart_top), (x, chart_bottom)], fill=(40, 70, 100), width=1)

        x_label = _format_time_tick(ts_value, span_seconds)
        x_box = draw.textbbox((0, 0), x_label, font=tick_font)
        x_w = x_box[2] - x_box[0]
        label_x = max(chart_left, min(chart_right - x_w, x - x_w // 2))
        x_label_candidates.append((label_x, x_label, x_w, ts_value))

    selected_labels: list[tuple[int, str, int]] = []
    last_label_right = -10_000
    for idx, (label_x, x_label, x_w, _ts_value) in enumerate(x_label_candidates):
        if idx == len(x_label_candidates) - 1:
            continue
        if label_x > last_label_right + 10:
            selected_labels.append((label_x, x_label, x_w))
            last_label_right = label_x + x_w

    if x_label_candidates:
        final_x, final_label, final_w, _ = x_label_candidates[-1]
        while selected_labels and final_x <= selected_labels[-1][0] + selected_labels[-1][2] + 10:
            selected_labels.pop()
        selected_labels.append((final_x, final_label, final_w))

    for label_x, x_label, _x_w in selected_labels:
        draw.text((label_x, chart_bottom + 12), x_label, fill=(188, 217, 240), font=tick_font)

    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=(214, 236, 255), width=2)
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=(214, 236, 255), width=2)
    draw.text((chart_right - 110, chart_bottom + 46), x_axis_label, fill=(214, 236, 255), font=label_font)
    draw.text((70, chart_bottom + 46), y_axis_label, fill=(214, 236, 255), font=label_font)

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
    rarity = normalize_rarity(getattr(loot, "rarity", "common"))
    base = calculate_item_points(
        item_name=str(loot.item_name),
        shiny=bool(loot.shiny),
        quantity=1,
        rarity=rarity,
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

    _append_current_time_point(x_values, y_values)

    subtitle = (
        f"{len(variant_rows)} variants tracked, {total} total pickups, "
        f"{_format_date(x_values[0])} → {_format_date(x_values[-1])}"
    )
    return _draw_line_chart(
        title=f"{display_name} - Season Item Graph",
        subtitle=subtitle,
        x_values=x_values,
        y_values=y_values,
        x_axis_label="Date (UTC)",
        y_axis_label="Total Items",
        y_axis_integers=True,
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

    _append_current_time_point(x_values, y_values)

    subtitle = f"PPE #{ppe.id} point progression from logged drops ({_format_date(x_values[0])} → {_format_date(x_values[-1])})"
    return _draw_line_chart(
        title=f"{display_name} - PPE #{ppe.id} Point Graph",
        subtitle=subtitle,
        x_values=x_values,
        y_values=y_values,
        x_axis_label="Date (UTC)",
        y_axis_label="Points",
    )
