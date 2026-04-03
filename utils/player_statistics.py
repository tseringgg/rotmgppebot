"""Wrapped-style season and character statistics helpers."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Iterable

import discord

from dataclass import Loot, PPEData, PlayerData
from utils.calc_points import normalize_item_name
from utils.points_service import (
    apply_percent_modifier,
    calculate_item_points,
    get_effective_modifier_bucket_for_ppe,
    get_ppe_type_multiplier_for_ppe,
)

_LOOT_CSV_PATH = Path("rotmg_loot_drops_updated.csv")


def _class_name(ppe: PPEData) -> str:
    return str(getattr(ppe.name, "value", ppe.name))


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _pick_phrase(options: list[str], *seed_values: float | int) -> str:
    """Pick a stable phrase variant so embeds feel less repetitive."""
    if not options:
        return ""

    seed = 0
    for idx, value in enumerate(seed_values, start=1):
        try:
            numeric = int(abs(float(value)) * 100)
        except (TypeError, ValueError):
            numeric = 0
        seed += numeric * idx * 31
    return options[seed % len(options)]


def _load_item_to_dungeon() -> dict[str, str]:
    mapping: dict[str, str] = {}

    try:
        with _LOOT_CSV_PATH.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                item_name = normalize_item_name(str(row.get("Item Name", "")).strip())
                dungeon_name = str(row.get("Dungeon", "")).strip()
                if not item_name or not dungeon_name:
                    continue

                # Preserve the first non-empty dungeon assignment for a given normalized item.
                mapping.setdefault(item_name, dungeon_name)
    except OSError:
        return {}

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


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _effective_drop_points_for_ppe(
    ppe: PPEData,
    *,
    item_name: str,
    shiny: bool,
    divine: bool,
    guild_config: dict | None,
) -> float:
    # Drop-level value with active class/season modifiers and PPE type multiplier.
    base_points = calculate_item_points(item_name=item_name, divine=divine, shiny=shiny, quantity=1)
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    adjusted = apply_percent_modifier(base_points, _safe_float(modifier_bucket.get("loot_percent")))
    adjusted = apply_percent_modifier(adjusted, _safe_float(modifier_bucket.get("total_percent")))
    adjusted *= get_ppe_type_multiplier_for_ppe(ppe, guild_config)
    return float(adjusted)


def _season_top_valued_finds(
    ppes: Iterable[PPEData],
    *,
    guild_config: dict | None,
) -> list[tuple[str, float, bool, bool, str, int]]:
    best_by_key: dict[tuple[str, bool, bool], tuple[str, float, bool, bool, str, int]] = {}

    for ppe in ppes:
        for entry in ppe.loot:
            item_name = str(entry.item_name)
            shiny = bool(entry.shiny)
            divine = bool(entry.divine)
            score = _effective_drop_points_for_ppe(
                ppe,
                item_name=item_name,
                shiny=shiny,
                divine=divine,
                guild_config=guild_config,
            )
            key = (normalize_item_name(item_name), shiny, divine)
            candidate = (item_name, score, shiny, divine, _class_name(ppe), int(ppe.id))
            existing = best_by_key.get(key)
            if existing is None or candidate[1] > existing[1]:
                best_by_key[key] = candidate

    scored = list(best_by_key.values())
    scored.sort(key=lambda row: (row[1], row[0].lower()), reverse=True)
    return scored[:3]


def _character_top_valued_drops(
    ppe: PPEData,
    *,
    guild_config: dict | None,
) -> list[tuple[str, float, bool, bool]]:
    scored: list[tuple[str, float, bool, bool]] = []
    for entry in ppe.loot:
        points = _effective_drop_points_for_ppe(
            ppe,
            item_name=str(entry.item_name),
            shiny=bool(entry.shiny),
            divine=bool(entry.divine),
            guild_config=guild_config,
        )
        scored.append((str(entry.item_name), float(points), bool(entry.shiny), bool(entry.divine)))

    scored.sort(key=lambda row: (row[1], row[0].lower()), reverse=True)
    return scored[:3]


def _season_performance_phrase(total_points: float, chars: int, unique_count: int) -> str:
    if chars <= 0:
        if unique_count <= 0:
            return _pick_phrase(
                [
                    "No active arc yet. Drop into your first run and start the story.",
                    "Fresh season slate. Spin up a character and get that first white logged.",
                    "Nothing tracked yet. Your highlight reel is still in pre-production.",
                ],
                total_points,
                chars,
                unique_count,
            )

        if unique_count >= 200:
            return _pick_phrase(
                [
                    "No characters, no problem. Your season loot stash is absurdly stacked.",
                    "Season-only grind is elite. You're speedrunning the loot museum.",
                    "You skipped the roster and still farmed a legendary season collection.",
                ],
                total_points,
                chars,
                unique_count,
            )
        if unique_count >= 120:
            return _pick_phrase(
                [
                    "Season-only tracker is cooking. Great coverage even without a main PPE yet.",
                    "Strong season item pool so far. Character arc can start whenever.",
                    "You're banking serious season value before committing to a roster.",
                ],
                total_points,
                chars,
                unique_count,
            )
        return _pick_phrase(
            [
                "Nice season-only start. Your first PPE arc will launch with a head start.",
                "Loot diary is awake even without a character run. Keep stacking uniques.",
                "Good early season tracking. Build the character roster when you're ready.",
            ],
            total_points,
            chars,
            unique_count,
        )

    avg = total_points / max(1, chars)
    if avg >= 350 or unique_count >= 200:
        return _pick_phrase(
            [
                "Legendary season! You're crushing the charts, but maybe you should touch grass.",
                "Top-tier run. The numbers are outrageous and the loot tab is glowing.",
                "Absolute heater season. You're farming highlights faster than recaps can load.",
            ],
            total_points,
            chars,
            unique_count,
        )
    if avg >= 140 or unique_count >= 120:
        return _pick_phrase(
            [
                "Momentum is up and your loot diary is healthy. You're on track for a great season.",
                "Clean progress across the board. Keep this pace and you'll finish strong.",
                "Strong mid-season form. Your account is building a serious trophy shelf.",
            ],
            total_points,
            chars,
            unique_count,
        )
    if avg >= 70 or unique_count >= 70:
        return _pick_phrase(
            [
                "Nice start. Keep it up and you might make something of yourself.",
                "Solid baseline season. One lucky streak and this jumps tiers fast.",
                "You're in the mix. Keep logging and the recap will look way juicier.",
            ],
            total_points,
            chars,
            unique_count,
        )
    return _pick_phrase(
        [
            "Slow season. The comeback montage is loading.",
            "Quiet start so far, but every run can flip the script.",
            "Low tempo right now. Queue up the redemption arc.",
        ],
        total_points,
        chars,
        unique_count,
    )


def _character_performance_phrase(ppe: PPEData, player_data: PlayerData) -> str:
    points = float(getattr(ppe, "points", 0.0) or 0.0)
    all_points = [float(getattr(char, "points", 0.0) or 0.0) for char in player_data.ppes]
    avg = (sum(all_points) / len(all_points)) if all_points else 0.0

    if points >= avg + 20:
        return _pick_phrase(
            [
                "This character is your chart-topper right now.",
                "Main-character energy detected. This one is carrying your board.",
                "Your MVP at the moment. This PPE keeps delivering.",
            ],
            points,
            avg,
            ppe.id,
        )
    if points <= max(0.0, avg - 20):
        return _pick_phrase(
            [
                "Underdog arc in progress. One cracked white and this flips fast.",
                "This one is behind pace, but a single heater session can rewrite it.",
                "Comeback candidate. Needs one big pop-off to catch the pack.",
            ],
            points,
            avg,
            ppe.id,
        )
    return _pick_phrase(
        [
            "Steady groove. This one is holding lane with the roster average.",
            "Reliable run. This character is tracking right around your season pace.",
            "Balanced arc so far. Not flashy, not falling off.",
        ],
        points,
        avg,
        ppe.id,
    )


def build_season_wrapped_embed(
    *,
    player_data: PlayerData,
    display_name: str,
    guild_config: dict | None = None,
) -> discord.Embed:
    """Build a Spotify Wrapped-style season summary embed."""
    ppes = list(player_data.ppes)
    all_loot = [loot for ppe in ppes for loot in ppe.loot]
    item_to_dungeon = _load_item_to_dungeon()
    season_items = getattr(player_data, "unique_items", set())

    total_points = sum(float(getattr(ppe, "points", 0.0) or 0.0) for ppe in ppes)
    total_drops = _total_logged_drops(all_loot)
    unique_count = len(season_items)
    shiny_uniques = sum(
        1
        for item in season_items
        if isinstance(item, (tuple, list)) and len(item) >= 2 and bool(item[1])
    )
    season_only_mode = (len(ppes) == 0 and unique_count > 0)
    tracked_drop_count = total_drops if total_drops > 0 else unique_count

    top_ppe = max(ppes, key=lambda p: float(getattr(p, "points", 0.0) or 0.0), default=None)
    low_ppe = min(ppes, key=lambda p: float(getattr(p, "points", 0.0) or 0.0), default=None)
    most_logged = _most_logged_item(all_loot)
    top_dungeon = _top_dungeon_from_loot(all_loot, item_to_dungeon)
    top_values = _season_top_valued_finds(ppes, guild_config=guild_config)

    embed = discord.Embed(
        title=f"{display_name}'s Season Wrapped",
        description="Your season recap is here. Here's some stats for you.",
        color=discord.Color.from_rgb(29, 185, 84),
    )
    embed.add_field(
        name="Season Vibe",
        value=_season_performance_phrase(total_points, len(ppes), unique_count),
        inline=False,
    )

    roster_line = f"Characters: **{len(ppes)}**\nSeason points: **{_format_points(total_points)}**\nUnique season items: **{unique_count}**"
    if season_only_mode:
        roster_line += "\nSeason-only tracker: **Enabled** (no active PPE yet)"
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
            f"Tracked drops: **{tracked_drop_count}**\n"
            f"Shiny uniques: **{shiny_uniques}**\n"
            f"Duplicate energy: **{max(0, tracked_drop_count - unique_count)}**"
        ),
        inline=True,
    )

    if top_values:
        lines = []
        for item_name, points, shiny, divine, class_name, ppe_id in top_values:
            tags: list[str] = []
            if shiny:
                tags.append("shiny")
            if divine:
                tags.append("divine")
            tag_text = f" [{' + '.join(tags)}]" if tags else ""
            lines.append(
                f"- {item_name}{tag_text} ({_format_points(points)} pts on {class_name} #{ppe_id})"
            )
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
    elif season_only_mode:
        embed.add_field(
            name="Weird But True",
            value=(
                "No character logs yet, but your season tracker already has "
                f"**{unique_count}** uniques. Pure season-loot speedrun behavior."
            ),
            inline=False,
        )

    embed.set_footer(text="PPE Wrapped: Season Edition")
    return embed


def build_character_wrapped_embed(
    *,
    player_data: PlayerData,
    ppe: PPEData,
    display_name: str,
    guild_config: dict | None = None,
) -> discord.Embed:
    """Build a Wrapped-style single-character summary embed."""
    loot_entries = list(ppe.loot)
    item_to_dungeon = _load_item_to_dungeon()

    total_drops = _total_logged_drops(loot_entries)
    unique_count = len({normalize_item_name(str(entry.item_name)) for entry in loot_entries if str(entry.item_name).strip()})
    shiny_count = sum(max(1, int(entry.quantity)) for entry in loot_entries if bool(entry.shiny)) if loot_entries else 0
    divine_count = sum(max(1, int(entry.quantity)) for entry in loot_entries if bool(entry.divine)) if loot_entries else 0

    most_logged = _most_logged_item(loot_entries)
    top_dungeon = _top_dungeon_from_loot(loot_entries, item_to_dungeon)
    top_values = _character_top_valued_drops(ppe, guild_config=guild_config)

    embed = discord.Embed(
        title=f"{display_name}'s {_class_name(ppe)} #{ppe.id} Wrapped",
        description=f"PPE #{ppe.id} ({_class_name(ppe)}) just got its reel.",
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
