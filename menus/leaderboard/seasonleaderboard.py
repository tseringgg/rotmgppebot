import csv
from functools import lru_cache
from pathlib import Path

import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.guild_config import load_guild_config
from utils.calc_points import normalize_item_name
from utils.player_records import load_player_records
from utils.season_loot_history import iter_season_variants

_LOOT_CSV_PATH = Path("rotmg_loot_drops_updated.csv")


@lru_cache(maxsize=1)
def _load_item_type_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    try:
        with _LOOT_CSV_PATH.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                item_name = normalize_item_name(str(row.get("Item Name", "")).strip()).casefold()
                loot_type = str(row.get("Loot Type", "")).strip().lower()
                if item_name:
                    lookup[item_name] = loot_type
    except OSError:
        return {}
    return lookup


def _count_season_items(records: object, *, exclude_limited: bool) -> int:
    type_lookup = _load_item_type_lookup()
    unique_items: set[tuple[str, bool]] = set()
    for item_name, shiny, _rarity, _timestamps in iter_season_variants(records):
        if exclude_limited and type_lookup.get(normalize_item_name(item_name).casefold()) == "limited":
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
        exclude_limited_from_counts = bool(contest_settings.get("contest_leaderboard_ignore_limited_items", False))

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            unique_count = _count_season_items(data, exclude_limited=exclude_limited_from_counts)
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
