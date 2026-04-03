"""Wrapped-style season and character statistics helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import discord

from dataclass import Loot, PPEData, PlayerData
from utils.calc_points import normalize_item_name
from utils.points_service import calculate_drop_points, load_loot_points

_DUNGEON_LOOT_PATH = Path("loot/dungeon_loot.json")


def _class_name(ppe: PPEData) -> str:
    return str(getattr(ppe.name, "value", ppe.name))


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _load_item_to_dungeon() -> dict[str, str]:
    try:
        with _DUNGEON_LOOT_PATH.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    mapping: dict[str, str] = {}
    for dungeon_name, dungeon_info in data.items():
        items = dungeon_info.get("items", []) if isinstance(dungeon_info, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                mapping[normalize_item_name(name)] = str(dungeon_name)
    return mapping


def _total_logged_drops(loot_entries: Iterable[Loot]) -> int:
    total = 0
    for entry in loot_entries:
        try:
            total += max(1, int(entry.quantity))
        except (TypeError, ValueError):
            total += 1
    return total


def _most_logged_item(loot_entries: Iterable[Loot]) -> tuple[str, int] | None:
    counts: Counter[str] = Counter()
    pretty_name: dict[str, str] = {}
    for entry in loot_entries:
        normalized = normalize_item_name(str(entry.item_name))
        if not normalized:
            continue
        pretty_name.setdefault(normalized, str(entry.item_name))
        try:
            quantity = max(1, int(entry.quantity))
        except (TypeError, ValueError):
            quantity = 1
        counts[normalized] += quantity

    if not counts:
        return None

    item_key, count = counts.most_common(1)[0]
    return pretty_name[item_key], int(count)


def _top_dungeon_from_loot(loot_entries: Iterable[Loot], item_to_dungeon: dict[str, str]) -> tuple[str, int] | None:
    dungeon_counts: Counter[str] = Counter()
    for entry in loot_entries:
        dungeon = item_to_dungeon.get(normalize_item_name(str(entry.item_name)))
        if not dungeon:
            continue
        try:
            quantity = max(1, int(entry.quantity))
        except (TypeError, ValueError):
            quantity = 1
        dungeon_counts[dungeon] += quantity

    if not dungeon_counts:
        return None

    dungeon, count = dungeon_counts.most_common(1)[0]
    return dungeon, int(count)


def _top_valued_unique_items(unique_items: set[tuple[str, bool]]) -> list[tuple[str, float, bool]]:
    loot_points = load_loot_points()
    scored: list[tuple[str, float, bool]] = []
    for item_name, shiny in unique_items:
        points = calculate_drop_points(item_name=item_name, divine=False, shiny=bool(shiny), loot_points=loot_points)
        scored.append((item_name, float(points), bool(shiny)))

    scored.sort(key=lambda row: (row[1], row[0].lower()), reverse=True)
    return scored[:3]


def _character_top_valued_drops(loot_entries: Iterable[Loot]) -> list[tuple[str, float, bool, bool]]:
    loot_points = load_loot_points()
    scored: list[tuple[str, float, bool, bool]] = []
    for entry in loot_entries:
        points = calculate_drop_points(
            item_name=entry.item_name,
            divine=bool(entry.divine),
            shiny=bool(entry.shiny),
            loot_points=loot_points,
        )
        scored.append((str(entry.item_name), float(points), bool(entry.shiny), bool(entry.divine)))

    scored.sort(key=lambda row: (row[1], row[0].lower()), reverse=True)
    return scored[:3]


def _season_performance_phrase(total_points: float, chars: int, unique_count: int) -> str:
    if chars <= 0:
        return "No active arc yet. Drop into your first run and start the story."

    avg = total_points / max(1, chars)
    if avg >= 70 or unique_count >= 80:
        return "Absolute heater. You are speedrunning main-character energy this season."
    if avg >= 35 or unique_count >= 40:
        return "Solid season pace. Momentum is up and your loot diary is healthy."
    return "Slow-burn season. The comeback montage is loading."


def _character_performance_phrase(ppe: PPEData, player_data: PlayerData) -> str:
    points = float(getattr(ppe, "points", 0.0) or 0.0)
    all_points = [float(getattr(char, "points", 0.0) or 0.0) for char in player_data.ppes]
    avg = (sum(all_points) / len(all_points)) if all_points else 0.0

    if points >= avg + 20:
        return "This character is your chart-topper right now."
    if points <= max(0.0, avg - 20):
        return "Underdog arc in progress. One cracked white and this flips fast."
    return "Steady groove. This one is holding lane with the roster average."


def build_season_wrapped_embed(*, player_data: PlayerData, display_name: str) -> discord.Embed:
    """Build a Spotify Wrapped-style season summary embed."""
    ppes = list(player_data.ppes)
    all_loot = [loot for ppe in ppes for loot in ppe.loot]
    item_to_dungeon = _load_item_to_dungeon()

    total_points = sum(float(getattr(ppe, "points", 0.0) or 0.0) for ppe in ppes)
    total_drops = _total_logged_drops(all_loot)
    unique_count = len(player_data.unique_items)
    shiny_uniques = sum(1 for _, shiny in player_data.unique_items if shiny)

    top_ppe = max(ppes, key=lambda p: float(getattr(p, "points", 0.0) or 0.0), default=None)
    low_ppe = min(ppes, key=lambda p: float(getattr(p, "points", 0.0) or 0.0), default=None)
    most_logged = _most_logged_item(all_loot)
    top_dungeon = _top_dungeon_from_loot(all_loot, item_to_dungeon)
    top_values = _top_valued_unique_items(player_data.unique_items)

    embed = discord.Embed(
        title=f"{display_name}'s Season Wrapped",
        description="Your season recap just dropped. Here are the weird, fun, and very real stats.",
        color=discord.Color.from_rgb(29, 185, 84),
    )
    embed.add_field(
        name="Season Vibe",
        value=_season_performance_phrase(total_points, len(ppes), unique_count),
        inline=False,
    )

    roster_line = f"Characters: **{len(ppes)}**\nSeason points: **{_format_points(total_points)}**\nUnique season items: **{unique_count}**"
    if top_ppe is not None:
        roster_line += (
            f"\nTop character: **{_class_name(top_ppe)} #{top_ppe.id}**"
            f" ({_format_points(float(getattr(top_ppe, 'points', 0.0) or 0.0))} pts)"
        )
    if low_ppe is not None and top_ppe is not None and low_ppe.id != top_ppe.id:
        roster_line += (
            f"\nNeeds a comeback: **{_class_name(low_ppe)} #{low_ppe.id}**"
            f" ({_format_points(float(getattr(low_ppe, 'points', 0.0) or 0.0))} pts)"
        )
    embed.add_field(name="Roster Snapshot", value=roster_line, inline=False)

    if most_logged:
        item_name, item_count = most_logged
        embed.add_field(name="Most Logged Item", value=f"**{item_name}** x{item_count}", inline=True)

    if top_dungeon:
        dungeon_name, dungeon_count = top_dungeon
        embed.add_field(name="White Factory", value=f"**{dungeon_name}** ({dungeon_count} logged drops)", inline=True)

    embed.add_field(
        name="Chaos Metrics",
        value=(
            f"Logged drops: **{total_drops}**\n"
            f"Shiny uniques: **{shiny_uniques}**\n"
            f"Duplicate energy: **{max(0, total_drops - unique_count)}**"
        ),
        inline=True,
    )

    if top_values:
        lines = []
        for item_name, points, shiny in top_values:
            suffix = " [shiny]" if shiny else ""
            lines.append(f"- {item_name}{suffix} ({_format_points(points)} pts)")
        embed.add_field(name="Most Valuable Finds", value="\n".join(lines), inline=False)

    if total_drops > 0:
        concentration = 0
        if most_logged:
            concentration = round((most_logged[1] / total_drops) * 100)
        weird_line = (
            f"One item alone makes up **{concentration}%** of all your logged drops. "
            "Collector behavior is officially detected."
        )
        embed.add_field(name="Weird But True", value=weird_line, inline=False)

    embed.set_footer(text="PPE Wrapped: Season Edition")
    return embed


def build_character_wrapped_embed(*, player_data: PlayerData, ppe: PPEData, display_name: str) -> discord.Embed:
    """Build a Spotify Wrapped-style single-character summary embed."""
    loot_entries = list(ppe.loot)
    item_to_dungeon = _load_item_to_dungeon()

    total_drops = _total_logged_drops(loot_entries)
    unique_count = len({normalize_item_name(str(entry.item_name)) for entry in loot_entries if str(entry.item_name).strip()})
    shiny_count = sum(max(1, int(entry.quantity)) for entry in loot_entries if bool(entry.shiny)) if loot_entries else 0
    divine_count = sum(max(1, int(entry.quantity)) for entry in loot_entries if bool(entry.divine)) if loot_entries else 0

    most_logged = _most_logged_item(loot_entries)
    top_dungeon = _top_dungeon_from_loot(loot_entries, item_to_dungeon)
    top_values = _character_top_valued_drops(loot_entries)

    embed = discord.Embed(
        title=f"{display_name}'s Character Wrapped",
        description=f"PPE #{ppe.id} ({_class_name(ppe)}) just got its highlight reel.",
        color=discord.Color.from_rgb(30, 215, 96),
    )

    embed.add_field(name="Character Arc", value=_character_performance_phrase(ppe, player_data), inline=False)
    embed.add_field(
        name="Overview",
        value=(
            f"Points: **{_format_points(float(getattr(ppe, 'points', 0.0) or 0.0))}**\n"
            f"Logged drops: **{total_drops}**\n"
            f"Unique logged items: **{unique_count}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="Sparkle Check",
        value=f"Shiny drops: **{shiny_count}**\nDivine drops: **{divine_count}**",
        inline=True,
    )

    if most_logged:
        embed.add_field(name="Most Logged Item", value=f"**{most_logged[0]}** x{most_logged[1]}", inline=True)

    if top_dungeon:
        embed.add_field(name="Main Dungeon", value=f"**{top_dungeon[0]}** ({top_dungeon[1]} drops)", inline=True)

    if top_values:
        lines: list[str] = []
        for item_name, points, shiny, divine in top_values:
            tags: list[str] = []
            if shiny:
                tags.append("shiny")
            if divine:
                tags.append("divine")
            tag_text = f" [{' + '.join(tags)}]" if tags else ""
            lines.append(f"- {item_name}{tag_text} ({_format_points(points)} pts/drop)")
        embed.add_field(name="Most Valuable Drops", value="\n".join(lines), inline=False)

    if total_drops and most_logged:
        focused = round((most_logged[1] / total_drops) * 100)
        embed.add_field(
            name="Strange Stat",
            value=f"**{focused}%** of this character's loot log is one item. That's commitment.",
            inline=False,
        )

    embed.set_footer(text="PPE Wrapped: Character Edition")
    return embed
