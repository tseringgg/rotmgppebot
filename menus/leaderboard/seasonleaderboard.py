from __future__ import annotations

from functools import lru_cache

import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.calc_points import load_loot_types, normalize_item_name
from utils.guild_config import get_contest_settings
from utils.player_records import load_player_records
from utils.season_loot_history import season_unique_items, unique_season_item_count


def _normalize_season_item_name(item_name: str) -> str:
    normalized = normalize_item_name(item_name).casefold()
    shiny_suffix = " (shiny)"
    if normalized.endswith(shiny_suffix):
        return normalized[: -len(shiny_suffix)].strip()
    return normalized


@lru_cache(maxsize=1)
def _limited_item_names() -> set[str]:
    return {
        _normalize_season_item_name(name)
        for name, loot_type in load_loot_types().items()
        if loot_type == "limited"
    }


def _is_limited_season_item(item_name: str) -> bool:
    return _normalize_season_item_name(item_name) in _limited_item_names()


def _season_unique_item_count_without_limited(player_data) -> int:
    return sum(1 for item_name, _shiny in season_unique_items(player_data) if not _is_limited_season_item(item_name))


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        contest_settings = await get_contest_settings(interaction)
        count_limited_items = bool(contest_settings.get("count_limited_items", True))
        records = await load_player_records(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            unique_count = (
                int(unique_season_item_count(data))
                if count_limited_items
                else int(_season_unique_item_count_without_limited(data))
            )
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
