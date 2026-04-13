"""State mutation helpers for /managequests actions."""

from __future__ import annotations

import discord

from menus.managequests.common import build_global_payload
from utils.guild_config import load_guild_config, save_guild_config
from utils.player_records import load_player_records, load_teams, save_player_records
from utils.quest_modes import build_team_quests_context, ensure_team_quests_state, normalize_team_key
from utils.calc_points import normalize_item_name
from utils.quest_manager import refresh_player_quests
from utils.season_loot_history import season_unique_items


async def save_settings(interaction: discord.Interaction, settings: dict) -> None:
    config = await load_guild_config(interaction)
    config["quest_settings"] = settings
    await save_guild_config(interaction, config)


def _normalized_member_owned_sets(player_data) -> tuple[set[str], set[str]]:
    owned_regular: set[str] = set()
    owned_shiny_targets: set[str] = set()
    for item_name, shiny in season_unique_items(player_data):
        normalized = normalize_item_name(item_name).lower()
        owned_regular.add(normalized)
        if shiny:
            owned_shiny_targets.add(f"{normalized} (shiny)")
    return owned_regular, owned_shiny_targets


def _intersect_completed_for_member(team_state: dict, player_data) -> tuple[list[str], list[str], list[str]]:
    owned_regular, owned_shiny_targets = _normalized_member_owned_sets(player_data)

    completed_items = [
        item
        for item in list(team_state.get("completed_items", []))
        if normalize_item_name(item).lower() in owned_regular
    ]
    completed_shinies = [
        item
        for item in list(team_state.get("completed_shinies", []))
        if normalize_item_name(item).lower() in owned_shiny_targets
    ]
    completed_skins = [
        item
        for item in list(team_state.get("completed_skins", []))
        if normalize_item_name(item).lower() in owned_regular
    ]
    return completed_items, completed_shinies, completed_skins


async def migrate_team_completed_to_members_on_disable(interaction: discord.Interaction, *, settings: dict) -> tuple[int, int]:
    """When team mode is disabled, map team completed quests into each member's own completed lists by ownership."""
    records = await load_player_records(interaction)
    teams = await load_teams(interaction)

    state_map = settings.get("team_quests_state", {})
    if not isinstance(state_map, dict):
        return 0, 0

    players_updated = 0
    completed_entries_written = 0

    for team_name, team_data in teams.items():
        team_key = str(team_name).strip().lower()
        team_state = state_map.get(team_key)
        if not isinstance(team_state, dict):
            continue

        for member_id in getattr(team_data, "members", []):
            player_data = records.get(int(member_id))
            if player_data is None or not player_data.is_member:
                continue

            matched_items, matched_shinies, matched_skins = _intersect_completed_for_member(team_state, player_data)
            quests = player_data.quests
            before_items = list(quests.completed_items)
            before_shinies = list(quests.completed_shinies)
            before_skins = list(quests.completed_skins)

            quests.completed_items = matched_items
            quests.completed_shinies = matched_shinies
            quests.completed_skins = matched_skins

            after_total = len(quests.completed_items) + len(quests.completed_shinies) + len(quests.completed_skins)
            completed_entries_written += after_total
            if before_items != matched_items or before_shinies != matched_shinies or before_skins != matched_skins:
                players_updated += 1

    if players_updated > 0:
        await save_player_records(interaction, records)

    return players_updated, completed_entries_written


def clear_active_quests_for_all_members(records: dict[int, object]) -> tuple[int, int]:
    """Clear active quest buckets for all member records and return (players_cleared, entries_removed)."""
    players_cleared = 0
    entries_removed = 0

    for player_data in records.values():
        if not getattr(player_data, "is_member", False):
            continue

        removed = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )
        if removed <= 0:
            continue

        player_data.quests.current_items.clear()
        player_data.quests.current_shinies.clear()
        player_data.quests.current_skins.clear()
        players_cleared += 1
        entries_removed += removed

    return players_cleared, entries_removed


def _quest_signature(player_data) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...], int | None]:
    quests = player_data.quests
    return (
        tuple(quests.current_items),
        tuple(quests.current_shinies),
        tuple(quests.current_skins),
        tuple(quests.completed_items),
        tuple(quests.completed_shinies),
        tuple(quests.completed_skins),
        player_data.quest_resets_remaining,
    )


async def apply_settings_to_players(
    interaction: discord.Interaction,
    *,
    settings: dict,
    reset_limit_changed: bool = False,
) -> tuple[int, int, int]:
    records = await load_player_records(interaction)
    teams = await load_teams(interaction)

    member_ids = [player_id for player_id, pdata in records.items() if pdata.is_member]
    before_signatures = {player_id: _quest_signature(records[player_id]) for player_id in member_ids}
    before_active_counts = {
        player_id: (
            len(records[player_id].quests.current_items)
            + len(records[player_id].quests.current_shinies)
            + len(records[player_id].quests.current_skins)
        )
        for player_id in member_ids
    }

    reset_counters_updated = 0

    for player_data in records.values():
        if not player_data.is_member:
            continue

        refresh_player_quests(
            player_data,
            target_item_quests=int(settings["regular_target"]),
            target_shiny_quests=int(settings["shiny_target"]),
            target_skin_quests=int(settings["skin_target"]),
            global_quests=build_global_payload(settings),
            team_quests=build_team_quests_context(
                settings=settings,
                player_data=player_data,
                records=records,
                teams=teams,
            ),
        )

        if reset_limit_changed:
            player_data.quest_resets_remaining = int(settings["num_resets"])
            reset_counters_updated += 1

    players_adjusted = 0
    active_entries_removed = 0
    for player_id in member_ids:
        player_data = records[player_id]
        after_signature = _quest_signature(player_data)
        after_active_count = (
            len(player_data.quests.current_items)
            + len(player_data.quests.current_shinies)
            + len(player_data.quests.current_skins)
        )

        if after_signature != before_signatures[player_id]:
            players_adjusted += 1
        if after_active_count < before_active_counts[player_id]:
            active_entries_removed += before_active_counts[player_id] - after_active_count

    if players_adjusted > 0 or reset_counters_updated > 0:
        await save_player_records(interaction, records)

    if bool(settings.get("enable_team_quests", False)) and not bool(settings.get("use_global_quests", False)):
        await save_settings(interaction, settings)

    return players_adjusted, active_entries_removed, reset_counters_updated


async def apply_selected_team_reset_actions(
    interaction: discord.Interaction,
    *,
    team_name: str,
    selected_values: set[str],
    active_item_quests: list[str],
    active_shiny_quests: list[str],
    active_skin_quests: list[str],
    action_reset_completed_items: str,
    action_reset_completed_shinies: str,
    action_reset_completed_skins: str,
    action_clear_all_info: str,
) -> dict:
    config = await load_guild_config(interaction)
    settings = config["quest_settings"]

    if bool(settings.get("use_global_quests", False)):
        return {"error": "global_mode"}
    if not bool(settings.get("enable_team_quests", False)):
        return {"error": "team_mode_disabled"}

    teams = await load_teams(interaction)
    records = await load_player_records(interaction)

    actual_team_name = None
    for candidate in teams:
        if str(candidate).lower() == str(team_name).lower():
            actual_team_name = candidate
            break
    if actual_team_name is None:
        return {"error": "team_not_found"}

    team_data = teams[actual_team_name]
    team_members = [records.get(int(member_id)) for member_id in getattr(team_data, "members", [])]
    team_members = [player_data for player_data in team_members if player_data is not None and player_data.is_member]
    if not team_members:
        return {"error": "no_team_members"}

    state_map = ensure_team_quests_state(settings)
    team_key = normalize_team_key(actual_team_name)
    state = state_map.get(team_key)
    if not isinstance(state, dict):
        state = {
            "current_items": [],
            "current_shinies": [],
            "current_skins": [],
            "completed_items": [],
            "completed_shinies": [],
            "completed_skins": [],
        }
        state_map[team_key] = state

    def _nameset(items: list[str]) -> set[str]:
        return {normalize_item_name(item).lower() for item in items}

    removed_current_items: list[str] = []
    removed_current_shinies: list[str] = []
    removed_current_skins: list[str] = []
    reset_completed_items = False
    reset_completed_shinies = False
    reset_completed_skins = False
    cleared_all_info = False

    state.setdefault("current_items", [])
    state.setdefault("current_shinies", [])
    state.setdefault("current_skins", [])
    state.setdefault("completed_items", [])
    state.setdefault("completed_shinies", [])
    state.setdefault("completed_skins", [])

    if action_clear_all_info in selected_values:
        state["current_items"] = []
        state["current_shinies"] = []
        state["current_skins"] = []
        state["completed_items"] = []
        state["completed_shinies"] = []
        state["completed_skins"] = []
        cleared_all_info = True
    else:
        if action_reset_completed_items in selected_values:
            state["completed_items"] = []
            reset_completed_items = True
        if action_reset_completed_shinies in selected_values:
            state["completed_shinies"] = []
            reset_completed_shinies = True
        if action_reset_completed_skins in selected_values:
            state["completed_skins"] = []
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
            target_set = _nameset(list(selected_item_set))
            before_items = list(state["current_items"])
            state["current_items"] = [q for q in state["current_items"] if normalize_item_name(q).lower() not in target_set]
            removed_current_items = [q for q in before_items if normalize_item_name(q).lower() in target_set]

        if selected_skin_set:
            target_set = _nameset(list(selected_skin_set))
            before_skins = list(state["current_skins"])
            state["current_skins"] = [q for q in state["current_skins"] if normalize_item_name(q).lower() not in target_set]
            removed_current_skins = [q for q in before_skins if normalize_item_name(q).lower() in target_set]

        if selected_shiny_set:
            target_set = _nameset(list(selected_shiny_set))
            before_shinies = list(state["current_shinies"])
            state["current_shinies"] = [q for q in state["current_shinies"] if normalize_item_name(q).lower() not in target_set]
            removed_current_shinies = [q for q in before_shinies if normalize_item_name(q).lower() in target_set]

    anchor_member = team_members[0]
    refresh_player_quests(
        anchor_member,
        target_item_quests=int(settings["regular_target"]),
        target_shiny_quests=int(settings["shiny_target"]),
        target_skin_quests=int(settings["skin_target"]),
        global_quests=build_global_payload(settings),
        team_quests=build_team_quests_context(
            settings=settings,
            player_data=anchor_member,
            records=records,
            teams=teams,
        ),
    )

    await save_guild_config(interaction, config)
    await save_player_records(interaction, records)

    return {
        "team_name": actual_team_name,
        "removed_current_items": removed_current_items,
        "removed_current_shinies": removed_current_shinies,
        "removed_current_skins": removed_current_skins,
        "reset_completed_items": reset_completed_items,
        "reset_completed_shinies": reset_completed_shinies,
        "reset_completed_skins": reset_completed_skins,
        "cleared_all_info": cleared_all_info,
    }


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
    settings["team_quests_state"] = {}
    if disable_global_mode:
        settings["use_global_quests"] = False

    records = await load_player_records(interaction)
    teams = await load_teams(interaction)
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
                team_quests=build_team_quests_context(
                    settings=settings,
                    player_data=player_data,
                    records=records,
                    teams=teams,
                ),
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

    config = await load_guild_config(interaction)
    settings = config["quest_settings"]
    team_mode_effective = bool(settings.get("enable_team_quests", False)) and not bool(settings.get("use_global_quests", False))

    if consume_reset_on_confirm and team_mode_effective and getattr(player_data, "team_name", None):
        team_summary = await apply_selected_team_reset_actions(
            interaction,
            team_name=str(player_data.team_name),
            selected_values=selected_values,
            active_item_quests=active_item_quests,
            active_shiny_quests=active_shiny_quests,
            active_skin_quests=active_skin_quests,
            action_reset_completed_items=action_reset_completed_items,
            action_reset_completed_shinies=action_reset_completed_shinies,
            action_reset_completed_skins=action_reset_completed_skins,
            action_clear_all_info=action_clear_all_info,
        )
        if team_summary.get("error"):
            return {"error": team_summary.get("error")}

        refreshed_records = await load_player_records(interaction)
        refreshed_player = refreshed_records.get(member_id)
        if refreshed_player is None or not refreshed_player.is_member:
            return {"error": "not_member"}

        refreshed_player.quest_resets_remaining = max(0, current_resets_remaining - 1)
        await save_player_records(interaction, refreshed_records)

        return {
            "removed_current_items": team_summary.get("removed_current_items", []),
            "removed_current_shinies": team_summary.get("removed_current_shinies", []),
            "removed_current_skins": team_summary.get("removed_current_skins", []),
            "reset_completed_items": bool(team_summary.get("reset_completed_items", False)),
            "reset_completed_shinies": bool(team_summary.get("reset_completed_shinies", False)),
            "reset_completed_skins": bool(team_summary.get("reset_completed_skins", False)),
            "cleared_all_info": bool(team_summary.get("cleared_all_info", False)),
            "reset_counter_to_default": False,
            "quest_resets_remaining": refreshed_player.quest_resets_remaining,
        }

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

    regular_target = int(config["quest_settings"]["regular_target"])
    shiny_target = int(config["quest_settings"]["shiny_target"])
    skin_target = int(config["quest_settings"]["skin_target"])
    teams = await load_teams(interaction)
    refresh_player_quests(
        player_data,
        target_item_quests=regular_target,
        target_shiny_quests=shiny_target,
        target_skin_quests=skin_target,
        global_quests=build_global_payload(config["quest_settings"]),
        team_quests=build_team_quests_context(
            settings=config["quest_settings"],
            player_data=player_data,
            records=records,
            teams=teams,
        ),
    )
    if bool(config["quest_settings"].get("enable_team_quests", False)) and not bool(config["quest_settings"].get("use_global_quests", False)):
        await save_guild_config(interaction, config)

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
