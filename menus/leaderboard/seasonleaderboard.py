from __future__ import annotations

import csv
import logging

import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.calc_points import normalize_item_name
from utils.guild_config import get_contest_settings
from utils.player_records import load_player_records
from utils.season_loot_history import season_unique_items


logger = logging.getLogger(__name__)
_LOOT_CSV_PATH = "rotmg_loot_drops_updated.csv"


def _normalize_season_item_name(item_name: str) -> str:
    normalized = normalize_item_name(item_name).casefold()
    shiny_suffix = " (shiny)"
    if normalized.endswith(shiny_suffix):
        return normalized[: -len(shiny_suffix)].strip()
    return normalized


def _limited_item_names() -> set[str]:
    limited_items: set[str] = set()
    try:
        with open(_LOOT_CSV_PATH, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                item_name = str(row.get("Item Name", "")).strip()
                loot_type = str(row.get("Loot Type", "")).strip().casefold()
                if not item_name or loot_type != "limited":
                    continue
                limited_items.add(_normalize_season_item_name(item_name))
    except FileNotFoundError:
        logger.warning("Season leaderboard limited-item lookup CSV not found at %s", _LOOT_CSV_PATH)
    except Exception:
        logger.exception("Failed to load limited-item names for the season leaderboard")

    logger.info("Loaded %d limited season items from %s", len(limited_items), _LOOT_CSV_PATH)
    return limited_items


def _is_limited_season_item(item_name: str, limited_item_names: set[str]) -> bool:
    return _normalize_season_item_name(item_name) in limited_item_names


def _season_unique_item_count_without_limited(player_data, limited_item_names: set[str]) -> int:
    return sum(1 for item_name, _shiny in season_unique_items(player_data) if not _is_limited_season_item(item_name, limited_item_names))


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return

    try:
        contest_settings = await get_contest_settings(interaction)
        count_limited_items = bool(contest_settings.get("count_limited_items", True))
        logger.info(
            "Season leaderboard requested for guild_id=%s count_limited_items=%s",
            getattr(interaction.guild, "id", None),
            count_limited_items,
        )

        records = await load_player_records(interaction)
        limited_item_names = _limited_item_names()

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue

            unique_items = season_unique_items(data)
            unique_count = len(unique_items)
            limited_count = 0

            if not count_limited_items:
                limited_count = sum(
                    1
                    for item_name, _shiny in unique_items
                    if _is_limited_season_item(item_name, limited_item_names)
                )
                unique_count -= limited_count

            if unique_count == 0:
                continue

            player = member_display_name(guild, pid)
            leaderboard_data.append((player, unique_count))

            if not count_limited_items and limited_count > 0:
                logger.info(
                    "Season leaderboard excluded %d limited items for player_id=%s player=%s",
                    limited_count,
                    pid,
                    player,
                )

        leaderboard_data.sort(key=lambda x: x[1], reverse=True)
        logger.info("Season leaderboard built with %d entries", len(leaderboard_data))

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
    except Exception:
        logger.exception("Season leaderboard failed")
        await send_error_response(interaction, "❌ Failed to build the season leaderboard. Check Railway deploy logs.")
