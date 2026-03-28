"""State mutation helpers for /managequests actions."""

from __future__ import annotations

import discord

from menus.managequests.common import build_global_payload
from utils.guild_config import load_guild_config, save_guild_config
from utils.player_records import load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests


async def save_settings(interaction: discord.Interaction, settings: dict) -> None:
    config = await load_guild_config(interaction)
    config["quest_settings"] = settings
    await save_guild_config(interaction, config)


async def apply_settings_to_players(
    interaction: discord.Interaction,
    *,
    settings: dict,
    reset_limit_changed: bool = False,
) -> tuple[int, int, int]:
    records = await load_player_records(interaction)

    players_adjusted = 0
    active_entries_removed = 0
    reset_counters_updated = 0

    for player_data in records.values():
        if not player_data.is_member:
            continue

        before_count = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )

        changed = refresh_player_quests(
            player_data,
            target_item_quests=int(settings["regular_target"]),
            target_shiny_quests=int(settings["shiny_target"]),
            target_skin_quests=int(settings["skin_target"]),
            global_quests=build_global_payload(settings),
        )

        after_count = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )

        if after_count < before_count:
            active_entries_removed += before_count - after_count
        if changed:
            players_adjusted += 1

        if reset_limit_changed:
            player_data.quest_resets_remaining = int(settings["num_resets"])
            reset_counters_updated += 1

    if players_adjusted > 0 or reset_counters_updated > 0:
        await save_player_records(interaction, records)

    return players_adjusted, active_entries_removed, reset_counters_updated


def clear_player_quest_data(player_data) -> int:
    """Clear all current/completed quest buckets and return number of entries removed."""
    cleared = (
        len(player_data.quests.current_items)
        + len(player_data.quests.current_shinies)
        + len(player_data.quests.current_skins)
        + len(player_data.quests.completed_items)
        + len(player_data.quests.completed_shinies)
        + len(player_data.quests.completed_skins)
    )

    player_data.quests.current_items.clear()
    player_data.quests.current_shinies.clear()
    player_data.quests.current_skins.clear()
    player_data.quests.completed_items.clear()
    player_data.quests.completed_shinies.clear()
    player_data.quests.completed_skins.clear()
    return cleared


async def clear_all_quests_and_global_pools(
    interaction: discord.Interaction,
    *,
    refill_random_quests: bool,
    disable_global_mode: bool,
) -> tuple[dict, int, int]:
    """
    Clear all players' quest data and global pools.

    When refill_random_quests is True, players are immediately refreshed into normal
    non-global random quest generation.
    """
    config = await load_guild_config(interaction)
    settings = dict(config["quest_settings"])

    settings["global_regular_quests"] = []
    settings["global_shiny_quests"] = []
    settings["global_skin_quests"] = []
    if disable_global_mode:
        settings["use_global_quests"] = False

    records = await load_player_records(interaction)
    players_updated = 0
    entries_cleared = 0

    for player_data in records.values():
        if not player_data.is_member:
            continue

        removed = clear_player_quest_data(player_data)
        if removed > 0:
            entries_cleared += removed
            players_updated += 1

        if refill_random_quests:
            changed = refresh_player_quests(
                player_data,
                target_item_quests=int(settings["regular_target"]),
                target_shiny_quests=int(settings["shiny_target"]),
                target_skin_quests=int(settings["skin_target"]),
                global_quests=build_global_payload(settings),
            )
            if changed and removed == 0:
                players_updated += 1

    config["quest_settings"] = settings
    await save_guild_config(interaction, config)
    await save_player_records(interaction, records)

    return settings, players_updated, entries_cleared
