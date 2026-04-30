"""Utilities for loot ops."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import discord

from dataclass import PPEData, PlayerData
from utils.guild_config import get_quest_targets, load_guild_config, save_guild_config
from utils.item_log_timestamps import seasonal_item_variant_key
from utils.message_utils.loot_table_md_builder import create_loot_markdown_file, create_season_loot_markdown_file
from utils.player_manager import player_manager
from utils.player_records import ensure_player_exists, load_player_records, load_teams, save_player_records
from utils.points_service import has_item_variant
from utils.quest_modes import build_global_quests_payload, build_team_quests_context
from utils.quest_manager import refresh_player_quests, remove_item_from_completed_quests, update_quests_for_item
from utils.season_loot_history import add_season_item_log, normalize_rarity, remove_season_item_log, unique_season_item_count
from datetime import datetime


@dataclass(frozen=True)
class PPELootOperationResult:
    item_name: str
    shiny: bool
    rarity: str
    username: str
    char_info: str
    old_points: float
    new_points: float
    points_delta: float
    ppe: PPEData
    quest_update: dict[str, Any]
    newly_completed_sets: list[tuple[str, str]] = None  # List of (set_name, set_type) tuples
    removed_sets: list[tuple[str, str]] = None  # List of (set_name, set_type) tuples for removed sets


@dataclass(frozen=True)
class SeasonLootOperationResult:
    item_name: str
    shiny: bool
    rarity: str
    username: str
    old_unique_total: int
    new_unique_total: int
    already_present: bool
    removed_count: int
    quest_update: dict[str, Any]
    player_data: PlayerData


def validate_item_variant(item_name: str, shiny: bool) -> None:
    if shiny and not has_item_variant(item_name, shiny=True):
        raise ValueError(f"❌ Shiny variant of `{item_name}` is not currently in bot.")


def validate_loot_input(item_name: str, *, shiny: bool, known_items: set[str] | list[str] | tuple[str, ...]) -> None:
    if item_name not in known_items:
        raise ValueError(
            f"❌ `{item_name}` is not a recognized item name.\n"
            "Use the autocomplete suggestions to select a valid item."
        )
    validate_item_variant(item_name, shiny)


def build_item_display_name(item_name: str, *, shiny: bool, rarity: str) -> str:
    prefix: list[str] = []
    rarity_value = normalize_rarity(rarity)
    if rarity_value != "common":
        prefix.append(rarity_value.title())
    if shiny:
        prefix.append("Shiny")
    prefix.append(item_name)
    return " ".join(prefix)


def build_char_info(ppe: PPEData) -> str:
    return f"PPE #{ppe.id} ({ppe.name})"


def _possessive(name: str) -> str:
    trimmed = str(name).strip()
    if not trimmed:
        return "User's"
    if trimmed.endswith("s"):
        return f"{trimmed}'"
    return f"{trimmed}'s"


def format_ppe_add_message(result: PPELootOperationResult) -> str:
    display_name = build_item_display_name(result.item_name, shiny=result.shiny, rarity=result.rarity)
    delta = result.points_delta
    delta_sign = f"+{delta}" if delta >= 0 else f"{delta}"
    lines: list[str] = []
    lines.append(
        f"✅ {display_name} added to {_possessive(result.username)} {result.char_info}."
    )
    lines.append(f"Points: {result.old_points} -> {result.new_points} ({delta_sign}).")

    # Quest completions
    quest_update = result.quest_update or {}
    completed_items = quest_update.get("completed_items", [])
    completed_shinies = quest_update.get("completed_shinies", [])
    completed_skins = quest_update.get("completed_skins", [])
    quest_lines: list[str] = []
    for i in completed_items:
        quest_lines.append(f"✅ Item quest completed: **{i}**")
    for s in completed_shinies:
        quest_lines.append(f"✨ Shiny quest completed: **{s}**")
    for k in completed_skins:
        quest_lines.append(f"✅ Skin quest completed: **{k}**")

    # Set completions
    set_lines: list[str] = []
    if result.newly_completed_sets:
        for set_name, set_type in result.newly_completed_sets:
            set_lines.append(f"🎉 Set Completed: **{set_name}** ({set_type})")

    # Only include quest/set section if there is something to show
    if quest_lines or set_lines:
        lines.append("")
        if set_lines:
            lines.extend(set_lines)
        if quest_lines:
            lines.extend(quest_lines)

    # Timestamp
    lines.append(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return "\n".join(lines)


def format_ppe_remove_message(result: PPELootOperationResult) -> str:
    display_name = build_item_display_name(result.item_name, shiny=result.shiny, rarity=result.rarity)
    delta = result.points_delta
    delta_sign = f"-{delta}" if delta >= 0 else f"{delta}"
    lines: list[str] = []
    lines.append(f"✅ {display_name} removed from {_possessive(result.username)} {result.char_info}.")
    lines.append(f"Points: {result.old_points} -> {result.new_points} ({delta_sign}).")

    # Removed sets
    if result.removed_sets:
        lines.append("")
        lines.append("🔔 Sets No Longer Completed:")
        for set_name, set_type in result.removed_sets:
            lines.append(f"- **{set_name}** ({set_type}) is no longer logged")

    # Timestamp
    lines.append(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return "\n".join(lines)


def format_season_add_message(result: SeasonLootOperationResult) -> str:
    display_name = build_item_display_name(result.item_name, shiny=result.shiny, rarity=result.rarity)
    lines: list[str] = []
    if result.already_present:
        lines.append(f"✅ {display_name} already existed in {result.username}'s seasonal loot; timestamp logged.")
    else:
        lines.append(f"✅ {display_name} is a new seasonal item for {result.username}.")
    lines.append(f"Unique items: {result.old_unique_total} -> {result.new_unique_total}.")

    # Quest completions when adding seasonal loot
    quest_update = result.quest_update or {}
    completed_items = quest_update.get("completed_items", [])
    completed_shinies = quest_update.get("completed_shinies", [])
    completed_skins = quest_update.get("completed_skins", [])
    quest_lines: list[str] = []
    for i in completed_items:
        quest_lines.append(f"✅ Item quest completed: **{i}**")
    for s in completed_shinies:
        quest_lines.append(f"✨ Shiny quest completed: **{s}**")
    for k in completed_skins:
        quest_lines.append(f"✅ Skin quest completed: **{k}**")

    if quest_lines:
        lines.append("")
        lines.extend(quest_lines)

    lines.append(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return "\n".join(lines)


def format_season_remove_message(result: SeasonLootOperationResult) -> str:
    display_name = build_item_display_name(result.item_name, shiny=result.shiny, rarity=result.rarity)
    lines: list[str] = []
    lines.append(f"✅ {display_name} removed from {result.username}'s seasonal loot.")
    lines.append(f"Unique items: {result.old_unique_total} -> {result.new_unique_total}.")
    lines.append(f"Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return "\n".join(lines)


async def add_ppe_loot(
    interaction: discord.Interaction,
    *,
    user: Any,
    ppe_id: int,
    item_name: str,
    shiny: bool,
    rarity: str,
) -> PPELootOperationResult:
    rarity_normalized = normalize_rarity(rarity)

    final_key, points_added, ppe, quest_update, newly_completed_sets = await player_manager.add_loot_and_points(
        interaction,
        user=user,
        ppe_id=ppe_id,
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
        points=0,
    )
    old_points = round(float(ppe.points) - float(points_added), 2)

    return PPELootOperationResult(
        item_name=final_key,
        shiny=shiny,
        rarity=rarity_normalized,
        username=getattr(user, "display_name", f"User {user.id}"),
        char_info=build_char_info(ppe),
        old_points=old_points,
        new_points=round(float(ppe.points), 2),
        points_delta=round(float(points_added), 2),
        ppe=ppe,
        quest_update=quest_update,
        newly_completed_sets=newly_completed_sets if newly_completed_sets else None,
    )


async def remove_ppe_loot(
    interaction: discord.Interaction,
    *,
    user: Any,
    ppe_id: int,
    item_name: str,
    shiny: bool,
    rarity: str,
) -> PPELootOperationResult:
    rarity_normalized = normalize_rarity(rarity)

    final_key, points_removed, ppe, removed_sets = await player_manager.remove_loot_and_points(
        interaction,
        user=user,
        ppe_id=ppe_id,
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
        points=0,
    )
    old_points = round(float(ppe.points) + float(points_removed), 2)

    return PPELootOperationResult(
        item_name=final_key,
        shiny=shiny,
        rarity=rarity_normalized,
        username=getattr(user, "display_name", f"User {user.id}"),
        char_info=build_char_info(ppe),
        old_points=old_points,
        new_points=round(float(ppe.points), 2),
        points_delta=round(float(points_removed), 2),
        ppe=ppe,
        quest_update={},
        removed_sets=removed_sets if removed_sets else None,
    )


async def add_season_loot(
    interaction: discord.Interaction,
    *,
    user_id: int,
    username: str,
    item_name: str,
    shiny: bool,
    rarity: str,
    update_quests: bool = True,
) -> SeasonLootOperationResult:
    rarity_normalized = normalize_rarity(rarity)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)

    if key not in records or not records[key].is_member:
        raise KeyError("❌ You're not part of the PPE contest.")

    player_data = records[key]
    old_unique = unique_season_item_count(player_data)
    variant_key = seasonal_item_variant_key(item_name, shiny, rarity_normalized)
    current_variant_logs = player_data.season_item_history.get(variant_key, [])
    already_present = bool(current_variant_logs)

    add_season_item_log(
        player_data,
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
    )

    quest_update: dict[str, Any] = {}
    if update_quests:
        regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
        config = await load_guild_config(interaction)
        quest_settings = config["quest_settings"]
        teams = await load_teams(interaction)
        team_context = build_team_quests_context(
            settings=quest_settings,
            player_data=player_data,
            records=records,
            teams=teams,
        )
        quest_update = update_quests_for_item(
            player_data,
            item_name,
            shiny,
            target_item_quests=regular_target,
            target_shiny_quests=shiny_target,
            target_skin_quests=skin_target,
            global_quests=build_global_quests_payload(quest_settings),
            team_quests=team_context,
        )
        if quest_update.get("team_state_changed"):
            await save_guild_config(interaction, config)

    new_unique = unique_season_item_count(player_data)
    await save_player_records(interaction, records)

    return SeasonLootOperationResult(
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
        username=username,
        old_unique_total=old_unique,
        new_unique_total=new_unique,
        already_present=already_present,
        removed_count=0,
        quest_update=quest_update,
        player_data=player_data,
    )


async def remove_season_loot(
    interaction: discord.Interaction,
    *,
    user_id: int,
    username: str,
    item_name: str,
    shiny: bool,
    rarity: str,
    update_quests: bool = True,
) -> SeasonLootOperationResult:
    rarity_normalized = normalize_rarity(rarity)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)

    if key not in records or not records[key].is_member:
        raise KeyError("❌ You're not part of the PPE contest.")

    player_data = records[key]
    old_unique = unique_season_item_count(player_data)

    removed = remove_season_item_log(
        player_data,
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
        remove_all=False,
    )
    if removed <= 0:
        raise ValueError(
            f"❌ **{item_name}{' (shiny)' if shiny else ''} [{rarity_normalized}]** is not in {username}'s season loot collection!"
        )

    quest_update: dict[str, Any] = {}
    if update_quests:
        removed_quest_entries = remove_item_from_completed_quests(player_data, item_name, shiny)
        regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
        config = await load_guild_config(interaction)
        quest_settings = config["quest_settings"]
        teams = await load_teams(interaction)
        team_context = build_team_quests_context(
            settings=quest_settings,
            player_data=player_data,
            records=records,
            teams=teams,
        )
        refresh_player_quests(
            player_data,
            target_item_quests=regular_target,
            target_shiny_quests=shiny_target,
            target_skin_quests=skin_target,
            global_quests=build_global_quests_payload(quest_settings),
            team_quests=team_context,
        )
        if bool(quest_settings.get("enable_team_quests", False)) and not bool(quest_settings.get("use_global_quests", False)):
            await save_guild_config(interaction, config)
        quest_update = removed_quest_entries

    new_unique = unique_season_item_count(player_data)
    await save_player_records(interaction, records)

    return SeasonLootOperationResult(
        item_name=item_name,
        shiny=shiny,
        rarity=rarity_normalized,
        username=username,
        old_unique_total=old_unique,
        new_unique_total=new_unique,
        already_present=False,
        removed_count=removed,
        quest_update=quest_update,
        player_data=player_data,
    )


def create_ppe_markdown_file(ppe: PPEData, guild_config: dict[str, Any] | None = None) -> str:
    return create_loot_markdown_file(ppe, guild_config=guild_config)


def create_season_markdown_file(player_data: PlayerData, *, display_name: str) -> str:
    return create_season_loot_markdown_file(player_data.season_item_history, display_name=display_name)


async def send_ppe_markdown_followup(
    interaction: discord.Interaction,
    *,
    ppe: PPEData,
    ephemeral: bool = True,
) -> None:
    guild_config = await load_guild_config(interaction)
    markdown_path = create_ppe_markdown_file(ppe, guild_config=guild_config)
    try:
        await interaction.followup.send(file=discord.File(markdown_path), ephemeral=ephemeral)
    finally:
        if os.path.exists(markdown_path):
            os.remove(markdown_path)


async def send_season_markdown_followup(
    interaction: discord.Interaction,
    *,
    player_data: PlayerData,
    display_name: str,
    ephemeral: bool = True,
) -> None:
    markdown_path = create_season_markdown_file(player_data, display_name=display_name)
    try:
        await interaction.followup.send(file=discord.File(markdown_path), ephemeral=ephemeral)
    finally:
        if os.path.exists(markdown_path):
            os.remove(markdown_path)
