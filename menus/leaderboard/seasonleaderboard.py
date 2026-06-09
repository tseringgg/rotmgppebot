import csv
from functools import lru_cache
from pathlib import Path
import re

import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.guild_config import load_guild_config
from utils.player_records import load_player_records
from utils.season_loot_history import iter_season_variants, unique_season_item_count

_LOOT_CSV_PATH = Path("rotmg_loot_drops_updated.csv")
_APOSTROPHE_VARIANTS = "\u2018\u2019\u02bc\u2032\u00b4`"
_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def _setting_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "on", "enabled"}
    return bool(value)


def _normalize_item_name(name: str) -> str:
    normalized = str(name or "")
    for apostrophe in _APOSTROPHE_VARIANTS:
        normalized = normalized.replace(apostrophe, "'")
    for dash in _DASH_VARIANTS:
        normalized = normalized.replace(dash, "-")
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return " ".join(normalized.split()).strip()


@lru_cache(maxsize=1)
def _load_limited_item_names() -> set[str]:
    limited_items: set[str] = set()
    
    # FIX 1: Changed encoding to "utf-8-sig" to strip invisible BOM characters
    with _LOOT_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            if str(row.get("Loot Type", "")).strip().casefold() != "limited":
                continue
            item_name = _normalize_item_name(str(row.get("Item Name", ""))).casefold()
            if item_name:
                limited_items.add(item_name)
    return limited_items


def _is_csv_limited_item(item_name: str, *, shiny: bool) -> bool:
    try:
        limited_items = _load_limited_item_names()
    except OSError as e:
        # FIX 2: Print the error so you know if the file path is wrong!
        print(f"[Leaderboard Warning] Failed to load limited items CSV: {e}")
        return False

    normalized_name = _normalize_item_name(item_name).casefold()
    if normalized_name in limited_items:
        return True
    if shiny and f"{normalized_name} (shiny)" in limited_items:
        return True
    return False


def _count_leaderboard_season_items(player_data: object, *, exclude_limited: bool) -> int:
    if not exclude_limited:
        return unique_season_item_count(player_data)

    unique_items: set[tuple[str, bool]] = set()
    for item_name, shiny, rarity, _timestamps in iter_season_variants(player_data):
        if str(rarity).strip().casefold() == "limited":
            continue
        if _is_csv_limited_item(item_name, shiny=shiny):
            continue
        unique_items.add((item_name, shiny))
    return len(unique_items)


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        records = await load_player_records(interaction)
        guild_config = await load_guild_config(interaction)
        contest_settings = (
            guild_config.get("contest_settings", {})
            if isinstance(guild_config, dict) and isinstance(guild_config.get("contest_settings", {}), dict)
            else {}
        )
        exclude_limited_from_counts = _setting_enabled(
            contest_settings.get("contest_leaderboard_ignore_limited_items", False)
        )
        print(f"[Leaderboard] Exclude limited items from counts: {exclude_limited_from_counts}")

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            unique_count = _count_leaderboard_season_items(data, exclude_limited=exclude_limited_from_counts)
            if unique_count == 0:
                continue

            player = member_display_name(guild, pid)
            leaderboard_data.append((player, unique_count))

        leaderboard_data.sort(key=lambda x: x[1], reverse=True)

        rows = [f"**{player}** — {count} unique items" for player, count in leaderboard_data]
        await send_leaderboard(
            interaction,
            title="Season Loot Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message=(
                "No season loot data available yet.\n"
                "Players can use `/addseasonloot` to start tracking unique items."
            ),
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
