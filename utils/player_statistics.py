"""Wrapped-style season and character statistics helpers."""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import discord

from dataclass import Loot, PPEData, PlayerData
from utils.calc_points import normalize_item_name
from utils.loot_constants import RARITY_CHOICES
from utils.points_service import (
    apply_percent_modifier,
    calculate_item_points,
    get_effective_modifier_bucket_for_ppe,
    loot_adjustments_for_ppe,
)
from utils.season_loot_history import iter_season_variants, normalize_rarity
from utils.set_operations import load_item_sets

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


from functools import lru_cache

@lru_cache(maxsize=1)
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


def _get_set_completion_field(ppe: PPEData) -> tuple[str, str, bool] | None:
    """Build a set completion field for a single PPE. Returns (name, value, inline) or None."""
    if not ppe.completed_sets:
        return None
    
    all_sets = load_item_sets()
    st_sets = [s for s in ppe.completed_sets if all_sets.get(s, {}).get("type") == "ST"]
    ut_sets = [s for s in ppe.completed_sets if all_sets.get(s, {}).get("type") == "UT"]
    
    lines = []
    if st_sets:
        lines.append(f"**ST Sets ({len(st_sets)}):** {', '.join(st_sets)}")
    if ut_sets:
        lines.append(f"**UT Sets ({len(ut_sets)}):** {', '.join(ut_sets)}")
    
    if lines:
        return ("Set Completions", "\n".join(lines), False)
    return None


def _get_quest_progress_field(player_data: PlayerData, guild_config: dict | None = None) -> tuple[str, str, bool] | None:
    """Build a quest progress field for a player. Returns (name, value, inline) or None."""
    quests = player_data.quests
    if not quests:
        return None
    
    config_dict = guild_config if guild_config else {}
    quest_settings = config_dict.get("quest_settings", {}) if isinstance(config_dict.get("quest_settings"), dict) else {}
    
    current = len(quests.current_items) + len(quests.current_shinies) + len(quests.current_skins)
    completed = len(quests.completed_items) + len(quests.completed_shinies) + len(quests.completed_skins)
    
    if current == 0 and completed == 0:
        return None
    
    quest_mode = "Regular"
    if bool(quest_settings.get("use_global_quests", False)):
        quest_mode = "Global"
    elif bool(quest_settings.get("enable_team_quests", False)):
        quest_mode = "Team"
    
    value = f"Mode: **{quest_mode}**\nActive: **{current}**\nCompleted: **{completed}**"
    return ("Quest Progress", value, True)


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


def _format_timestamp(ts: int | None) -> str:
    if ts is None:
        return "n/a"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError):
        return "n/a"


def _format_duration(seconds: int | float) -> str:
    try:
        total = max(0, int(seconds))
    except (TypeError, ValueError):
        return "0h"

    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _sorted_positive_timestamps(raw_timestamps: Iterable[int]) -> list[int]:
    parsed: list[int] = []
    for raw in raw_timestamps:
        try:
            ts = int(raw)
        except (TypeError, ValueError):
            continue
        if ts > 0:
            parsed.append(ts)
    parsed.sort()
    return parsed


def _largest_gap_seconds(raw_timestamps: Iterable[int]) -> int:
    timestamps = _sorted_positive_timestamps(raw_timestamps)
    if len(timestamps) < 2:
        return 0

    largest = 0
    prev = timestamps[0]
    for current in timestamps[1:]:
        largest = max(largest, current - prev)
        prev = current
    return max(0, largest)


def _stable_pick_optional_fields(
    candidates: list[tuple[str, str, bool]],
    *,
    min_fields: int,
    max_fields: int,
    seed_values: tuple[float | int, ...],
) -> list[tuple[str, str, bool]]:
    available = [c for c in candidates if c[1]]
    if not available:
        return []

    low = max(0, int(min_fields))
    high = max(low, int(max_fields))
    target = min(len(available), max(low, high))
    if high > low:
        chooser = _pick_phrase([str(n) for n in range(low, high + 1)], *seed_values)
        try:
            target = min(len(available), int(chooser))
        except (TypeError, ValueError):
            target = min(len(available), high)

    rotation = 0
    if available:
        seed = 0
        for idx, value in enumerate(seed_values, start=1):
            try:
                numeric = int(abs(float(value)) * 100)
            except (TypeError, ValueError):
                numeric = 0
            seed += numeric * idx * 17
        rotation = seed % len(available)

    rotated = available[rotation:] + available[:rotation]
    return rotated[:target]


def _timing_summary(timestamps: Iterable[int], total_events: int) -> tuple[str, str, str] | None:
    parsed = _sorted_positive_timestamps(timestamps)
    if not parsed:
        return None

    start = parsed[0]
    end = parsed[-1]
    span_seconds = max(0, end - start)
    span_days = max(1.0, span_seconds / 86400.0)
    cadence = total_events / span_days if total_events > 0 else 0.0

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    since_last = max(0, now_ts - end)
    longest_gap = _largest_gap_seconds(parsed)

    if since_last <= 86400:
        recency = "fresh"
    elif since_last <= 3 * 86400:
        recency = "warm"
    elif since_last <= 10 * 86400:
        recency = "cooling"
    else:
        recency = "dormant"

    cadence_line = f"Active span: **{_format_duration(span_seconds)}** | Pace: **{cadence:.1f} logs/day**"
    recency_line = f"Last activity: **{_format_duration(since_last)} ago** ({recency})"
    drought_line = f"Longest drought: **{_format_duration(longest_gap)}**"
    return cadence_line, recency_line, drought_line


def _rarity_quality_line(*, rarity_counts: Counter[str], total_events: int, shiny_count: int = 0) -> str:
    if total_events <= 0:
        return "No rarity signal yet. First white bag could change everything."

    legendary = int(rarity_counts.get("legendary", 0))
    divine = int(rarity_counts.get("divine", 0))
    premium = legendary + divine
    premium_share = (premium / total_events) * 100 if total_events else 0.0
    divine_share = (divine / total_events) * 100 if total_events else 0.0

    if premium_share >= 45 or divine_share >= 12:
        opener = "Loot quality is outrageous."
    elif premium_share >= 28 or divine_share >= 7:
        opener = "Strong quality curve."
    elif premium_share >= 15:
        opener = "Healthy quality profile."
    elif premium_share >= 8:
        opener = "Steady quality, room to spike."
    else:
        opener = "Mostly bread-and-butter drops so far."

    shiny_note = ""
    if shiny_count > 0:
        shiny_note = f" Shiny pressure: **{shiny_count}**."

    return (
        f"{opener} Premium bags: **{premium_share:.1f}%** "
        f"(legendary+divine), divine rate: **{divine_share:.1f}%**.{shiny_note}"
    )


def _season_time_span(variants: Iterable[tuple[str, bool, str, list[int]]]) -> tuple[int | None, int | None]:
    timestamps: list[int] = []
    for _item_name, _shiny, _rarity, item_timestamps in variants:
        for raw_ts in item_timestamps:
            try:
                parsed_ts = int(raw_ts)
            except (TypeError, ValueError):
                continue
            if parsed_ts > 0:
                timestamps.append(parsed_ts)
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def _rarity_breakdown(variants: Iterable[tuple[str, bool, str, list[int]]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for _item_name, _shiny, rarity, timestamps in variants:
        counts[normalize_rarity(rarity)] += sum(1 for ts in timestamps if int(ts) > 0)
    return counts


def _effective_drop_points_for_ppe(
    ppe: PPEData,
    *,
    item_name: str,
    shiny: bool,
    rarity: str,
    guild_config: dict | None,
) -> float:
    # Drop-level value with item-only class/season and PPE multipliers.
    base_points = calculate_item_points(item_name=item_name, shiny=shiny, quantity=1, rarity=rarity)
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    adjustments = loot_adjustments_for_ppe(ppe, guild_config)
    adjusted = apply_percent_modifier(base_points, _safe_float(modifier_bucket.get("loot_percent")))
    adjusted = apply_percent_modifier(adjusted, _safe_float(modifier_bucket.get("total_percent")))
    adjusted *= _safe_float(adjustments.get("reduction_multiplier"))
    adjusted *= _safe_float(adjustments.get("type_multiplier"))
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
            rarity = normalize_rarity(getattr(entry, "rarity", "common"))
            divine = rarity == "divine"
            score = _effective_drop_points_for_ppe(
                ppe,
                item_name=item_name,
                shiny=shiny,
                rarity=rarity,
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
        rarity = normalize_rarity(getattr(entry, "rarity", "common"))
        divine = rarity == "divine"
        points = _effective_drop_points_for_ppe(
            ppe,
            item_name=str(entry.item_name),
            shiny=bool(entry.shiny),
            rarity=rarity,
            guild_config=guild_config,
        )
        scored.append((str(entry.item_name), float(points), bool(entry.shiny), divine))

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
    if avg >= 1400 or unique_count >= 420:
        return _pick_phrase(
            [
                "This season was fully unhinged. White bags drop like rain when you log in.",
                "Mythic season. I wish I was as spoonfed as you.",
                "Touch-grass alert. You turned the season into a full-time raid career.",
            ],
            total_points,
            chars,
            unique_count,
        )
    if avg >= 750 or unique_count >= 320:
        return _pick_phrase(
            [
                "Elite detected. Your loot is insane.",
                "You are farming at a pace that makes you suspicious.",
                "Ridiculous output. Oryx probably knows your name by now.",
            ],
            total_points,
            chars,
            unique_count,
        )
    if avg >= 500 or unique_count >= 260:
        return _pick_phrase(
            [
                "Solid season. You're likely part-time employed though.",
                "Big numbers, big coverage, big pressure on everyone else.",
                "You are speedrunning white bags this season.",
            ],
            total_points,
            chars,
            unique_count,
        )
    if avg >= 350 or unique_count >= 200:
        return _pick_phrase(
            [
                "Decent season! Keep it up.",
                "The numbers are outrageous and the loot tab is glowing. You're getting there.",
                "You're farming highlights faster than recaps can load.",
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

    if points >= max(avg + 140, 520):
        return _pick_phrase(
            [
                "Transcendent run. This character is printing white-bag headlines.",
                "This PPE is on deity mode. Touch grass after this dungeon chain.",
                "Realm final boss energy. This arc is way above league average.",
            ],
            points,
            avg,
            ppe.id,
        )
    if points >= max(avg + 80, 320):
        return _pick_phrase(
            [
                "Hard-carry status. This one is dragging your board upward.",
                "Heater character. White bag momentum is very real here.",
                "This PPE is doing the heavy lifting for your season stats.",
            ],
            points,
            avg,
            ppe.id,
        )
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
    if points <= max(0.0, avg - 120):
        return _pick_phrase(
            [
                "Deep rebuild arc. Even Thessal would call this a rough patch.",
                "This run is in hard recovery mode. Needs a serious white bag swing.",
                "Bottom-tier tempo right now. Time to wake up the grind.",
            ],
            points,
            avg,
            ppe.id,
        )
    if points <= max(0.0, avg - 60):
        return _pick_phrase(
            [
                "Behind the roster pace. One good event chain can fix it.",
                "This one is lagging. Queue a comeback session.",
                "Under target right now, but still one streak away from relevance.",
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
    season_variants = iter_season_variants(player_data)
    season_items = {(item_name, shiny) for item_name, shiny, _rarity, _timestamps in season_variants}
    season_start, season_end = _season_time_span(season_variants)
    rarity_breakdown = _rarity_breakdown(season_variants)
    season_timestamps = [
        ts
        for _item_name, _shiny, _rarity, timestamps in season_variants
        for ts in timestamps
    ]

    total_points = sum(float(getattr(ppe, "points", 0.0) or 0.0) for ppe in ppes)
    total_drops = _total_logged_drops(all_loot)
    unique_count = len(season_items)
    season_pickups = sum(len(timestamps) for _item_name, _shiny, _rarity, timestamps in season_variants)
    shiny_uniques = sum(
        1
        for item in season_items
        if isinstance(item, (tuple, list)) and len(item) >= 2 and bool(item[1])
    )
    season_only_mode = (len(ppes) == 0 and unique_count > 0)
    tracked_drop_count = total_drops if total_drops > 0 else season_pickups

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

    embed.add_field(
        name="Season Timeline",
        value=f"First log: **{_format_timestamp(season_start)}**\nLast log: **{_format_timestamp(season_end)}**",
        inline=False,
    )

    season_timing = _timing_summary(season_timestamps, max(tracked_drop_count, season_pickups))
    rarity_spread_line = "\n".join(
        f"{rarity.title()}: **{rarity_breakdown.get(rarity, 0)}**"
        for rarity in RARITY_CHOICES
    )
    quality_line = _rarity_quality_line(
        rarity_counts=rarity_breakdown,
        total_events=max(1, season_pickups),
        shiny_count=shiny_uniques,
    )

    candidate_fields: list[tuple[str, str, bool]] = []
    if rarity_breakdown:
        candidate_fields.append(("Rarity Spread", rarity_spread_line, True))
    candidate_fields.append(("Loot Quality", quality_line, False))

    if season_timing:
        candidate_fields.append(("Season Pace", f"{season_timing[0]}\n{season_timing[1]}", False))
        candidate_fields.append(("Downtime Check", season_timing[2], True))

    if most_logged:
        item_name, item_count = most_logged
        concentration = 0
        if tracked_drop_count > 0:
            concentration = round((item_count / tracked_drop_count) * 100)
        candidate_fields.append(("Most Logged Item", f"**{item_name}** x{item_count}", True))
        candidate_fields.append(
            (
                "Weird But True",
                (
                    f"**{item_name}** is **{concentration}%** of your tracked drops. "
                    "Bag tunnel vision is real."
                ),
                False,
            )
        )
    elif season_only_mode:
        candidate_fields.append(
            (
                "Weird But True",
                (
                    "No character logs yet, but your season tracker already has "
                    f"**{unique_count}** uniques. Pure season-loot speedrun behavior."
                ),
                False,
            )
        )

    if top_dungeon:
        dungeon_name, dungeon_count = top_dungeon
        candidate_fields.append(("White Factory", f"**{dungeon_name}** ({dungeon_count} logged drops)", True))

    candidate_fields.append(
        (
            "Chaos Metrics",
            (
                f"Tracked drops: **{tracked_drop_count}**\n"
                f"Shiny uniques: **{shiny_uniques}**\n"
                f"Season pickups: **{season_pickups}**\n"
                f"Duplicate energy: **{max(0, tracked_drop_count - unique_count)}**"
            ),
            True,
        )
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
        candidate_fields.append(("Most Valuable Finds", "\n".join(lines), False))

    # Add set completion information if any sets are completed
    if ppes:
        for ppe in ppes:
            set_field = _get_set_completion_field(ppe)
            if set_field:
                candidate_fields.append(set_field)
                break  # Only show one character's sets per page

    # Add quest progress information
    quest_field = _get_quest_progress_field(player_data, guild_config)
    if quest_field:
        candidate_fields.append(quest_field)

    selected = _stable_pick_optional_fields(
        candidate_fields,
        min_fields=4,
        max_fields=6,
        seed_values=(total_points, len(ppes), unique_count, tracked_drop_count, season_pickups),
    )
    for name, value, inline in selected:
        embed.add_field(name=name, value=value, inline=inline)

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
    loot_times: list[int] = []
    rarity_counts: Counter[str] = Counter()

    for entry in loot_entries:
        try:
            quantity = max(1, int(getattr(entry, "quantity", 1)))
        except (TypeError, ValueError):
            quantity = 1
        rarity_counts[normalize_rarity(getattr(entry, "rarity", None))] += quantity

        for raw_ts in getattr(entry, "logged_times", []):
            try:
                parsed_ts = int(raw_ts)
            except (TypeError, ValueError):
                continue
            if parsed_ts > 0:
                loot_times.append(parsed_ts)

    loot_start, loot_end = (min(loot_times), max(loot_times)) if loot_times else (None, None)

    total_drops = _total_logged_drops(loot_entries)
    unique_count = len({normalize_item_name(str(entry.item_name)) for entry in loot_entries if str(entry.item_name).strip()})
    shiny_count = sum(max(1, int(entry.quantity)) for entry in loot_entries if bool(entry.shiny)) if loot_entries else 0
    divine_count = (
        sum(max(1, int(entry.quantity)) for entry in loot_entries if normalize_rarity(getattr(entry, "rarity", "common")) == "divine")
        if loot_entries
        else 0
    )

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

    embed.add_field(
        name="Loot Timeline",
        value=f"First log: **{_format_timestamp(loot_start)}**\nLast log: **{_format_timestamp(loot_end)}**",
        inline=True,
    )

    timing_summary = _timing_summary(loot_times, total_drops)
    rarity_spread = "\n".join(
        f"{rarity.title()}: **{rarity_counts.get(rarity, 0)}**"
        for rarity in RARITY_CHOICES
    )
    quality_line = _rarity_quality_line(
        rarity_counts=rarity_counts,
        total_events=max(1, total_drops),
        shiny_count=shiny_count,
    )

    char_candidates: list[tuple[str, str, bool]] = []
    char_candidates.append(("Rarity Spread", rarity_spread, False))
    char_candidates.append(("Loot Quality", quality_line, False))

    if timing_summary:
        char_candidates.append(("Run Cadence", f"{timing_summary[0]}\n{timing_summary[1]}", False))
        char_candidates.append(("Longest Dry Spell", timing_summary[2], True))

    if most_logged:
        char_candidates.append(("Most Logged Item", f"**{most_logged[0]}** x{most_logged[1]}", True))
        if total_drops:
            focused = round((most_logged[1] / total_drops) * 100)
            char_candidates.append(
                (
                    "Strange Stat",
                    f"**{focused}%** of this character's loot log is one item. That's commitment.",
                    False,
                )
            )

    if top_dungeon:
        char_candidates.append(("Main Dungeon", f"**{top_dungeon[0]}** ({top_dungeon[1]} drops)", True))

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
        char_candidates.append(("Most Valuable Drops", "\n".join(lines), False))

    # Add set completion information
    set_field = _get_set_completion_field(ppe)
    if set_field:
        char_candidates.append(set_field)

    # Add quest progress information
    quest_field = _get_quest_progress_field(player_data, guild_config)
    if quest_field:
        char_candidates.append(quest_field)

    selected_character_fields = _stable_pick_optional_fields(
        char_candidates,
        min_fields=4,
        max_fields=6,
        seed_values=(float(getattr(ppe, "points", 0.0) or 0.0), total_drops, unique_count, ppe.id),
    )
    for name, value, inline in selected_character_fields:
        embed.add_field(name=name, value=value, inline=inline)

    embed.set_footer(text="PPE Wrapped: Character Edition")
    return embed
