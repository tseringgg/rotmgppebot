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


async def apply_selected_reset_actions(
    interaction: discord.Interaction,
    *,
    member_id: int,
    selected_values: set[str],
    active_item_quests: list[str],
    active_shiny_quests: list[str],
    active_skin_quests: list[str],
    default_reset_limit: int,
    consume_reset_on_confirm: bool,
    include_reset_counter_option: bool,
    action_reset_completed_items: str,
    action_reset_completed_shinies: str,
    action_reset_completed_skins: str,
    action_clear_all_info: str,
    action_reset_resets_to_default: str,
) -> dict:
    records = await load_player_records(interaction)
    if member_id not in records or not records[member_id].is_member:
        return {"error": "not_member"}

    player_data = records[member_id]
    value = player_data.quest_resets_remaining
    if value is None:
        current_resets_remaining = max(0, default_reset_limit)
    else:
        try:
            current_resets_remaining = max(0, int(value))
        except (TypeError, ValueError):
            current_resets_remaining = max(0, default_reset_limit)

    if player_data.quest_resets_remaining != current_resets_remaining:
        player_data.quest_resets_remaining = current_resets_remaining

    if consume_reset_on_confirm and current_resets_remaining <= 0:
        await save_player_records(interaction, records)
        return {"error": "no_resets"}

    quests = player_data.quests

    removed_current_items: list[str] = []
    removed_current_shinies: list[str] = []
    removed_current_skins: list[str] = []
    reset_completed_items = False
    reset_completed_shinies = False
    reset_completed_skins = False
    cleared_all_info = False
    reset_counter_to_default = False

    if action_clear_all_info in selected_values:
        quests.current_items.clear()
        quests.current_shinies.clear()
        quests.current_skins.clear()
        quests.completed_items.clear()
        quests.completed_shinies.clear()
        quests.completed_skins.clear()
        cleared_all_info = True
    else:
        if action_reset_completed_items in selected_values:
            quests.completed_items.clear()
            reset_completed_items = True
        if action_reset_completed_shinies in selected_values:
            quests.completed_shinies.clear()
            reset_completed_shinies = True
        if action_reset_completed_skins in selected_values:
            quests.completed_skins.clear()
            reset_completed_skins = True

        selected_item_indexes = {
            int(value.split("::", 1)[1])
            for value in selected_values
            if value.startswith("item_idx::")
        }
        selected_skin_indexes = {
            int(value.split("::", 1)[1])
            for value in selected_values
            if value.startswith("skin_idx::")
        }
        selected_shiny_indexes = {
            int(value.split("::", 1)[1])
            for value in selected_values
            if value.startswith("shiny_idx::")
        }

        selected_item_set = {
            active_item_quests[idx]
            for idx in selected_item_indexes
            if 0 <= idx < len(active_item_quests)
        }
        selected_skin_set = {
            active_skin_quests[idx]
            for idx in selected_skin_indexes
            if 0 <= idx < len(active_skin_quests)
        }
        selected_shiny_set = {
            active_shiny_quests[idx]
            for idx in selected_shiny_indexes
            if 0 <= idx < len(active_shiny_quests)
        }

        if selected_item_set:
            before = list(quests.current_items)
            quests.current_items = [q for q in quests.current_items if q not in selected_item_set]
            removed_current_items = [q for q in before if q in selected_item_set]

        if selected_skin_set:
            before = list(quests.current_skins)
            quests.current_skins = [q for q in quests.current_skins if q not in selected_skin_set]
            removed_current_skins = [q for q in before if q in selected_skin_set]

        if selected_shiny_set:
            before = list(quests.current_shinies)
            quests.current_shinies = [q for q in quests.current_shinies if q not in selected_shiny_set]
            removed_current_shinies = [q for q in before if q in selected_shiny_set]

    config = await load_guild_config(interaction)
    regular_target = int(config["quest_settings"]["regular_target"])
    shiny_target = int(config["quest_settings"]["shiny_target"])
    skin_target = int(config["quest_settings"]["skin_target"])
    refresh_player_quests(
        player_data,
        target_item_quests=regular_target,
        target_shiny_quests=shiny_target,
        target_skin_quests=skin_target,
        global_quests=build_global_payload(config["quest_settings"]),
    )

    if include_reset_counter_option and action_reset_resets_to_default in selected_values:
        player_data.quest_resets_remaining = default_reset_limit
        reset_counter_to_default = True

    if consume_reset_on_confirm:
        player_data.quest_resets_remaining = max(0, current_resets_remaining - 1)

    await save_player_records(interaction, records)

    return {
        "removed_current_items": removed_current_items,
        "removed_current_shinies": removed_current_shinies,
        "removed_current_skins": removed_current_skins,
        "reset_completed_items": reset_completed_items,
        "reset_completed_shinies": reset_completed_shinies,
        "reset_completed_skins": reset_completed_skins,
        "cleared_all_info": cleared_all_info,
        "reset_counter_to_default": reset_counter_to_default,
        "quest_resets_remaining": player_data.quest_resets_remaining,
    }
