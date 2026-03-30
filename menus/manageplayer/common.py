"""Shared helpers for the /manageplayer admin menu flow."""

from __future__ import annotations

import os

import discord

from dataclass import PPEData, PlayerData
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils import SafeResponse
from menus.myinfo.common import (
    build_character_embed,
    display_class_name,
    format_points,
    penalty_input_defaults,
)
from utils.guild_config import load_guild_config
from utils.loot_table_md_builder import create_season_loot_markdown_file
from utils.ppe_list_md_builder import create_ppe_list_markdown_file


async def close_manageplayer_menu(interaction: discord.Interaction) -> None:
    await SafeResponse.close(interaction, close_message="Closed /manageplayer menu.")


async def send_followup_text(interaction: discord.Interaction, content: str, *, ephemeral: bool = True) -> None:
    await SafeResponse.send_text(interaction, content, ephemeral=ephemeral)

def target_home_embed(
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
    active_ppe: PPEData | None,
    max_ppes: int,
    target_is_admin: bool,
) -> discord.Embed:
    best_ppe = max(player_data.ppes, key=lambda p: float(p.points), default=None)

    if best_ppe:
        best_line = f"PPE #{best_ppe.id} ({display_class_name(best_ppe)}): {format_points(best_ppe.points)}"
    else:
        best_line = "None"

    if active_ppe:
        active_line = f"PPE #{active_ppe.id} ({display_class_name(active_ppe)}): {format_points(active_ppe.points)}"
    else:
        active_line = "No active PPE"

    embed = discord.Embed(
        title=f"Manage Player - {target.display_name}",
        description=(
            "Admin management dashboard for this player. "
            "All changes made from this panel are posted publicly."
        ),
        color=discord.Color.dark_teal(),
    )
    if target_is_admin:
        ppe_role_text = "Is PPE Admin"
    elif player_data.team_name:
        ppe_role_text = "Is Team PPE"
    else:
        ppe_role_text = "Regular PPE Player"

    embed.add_field(name="Discord ID", value=str(target.user_id), inline=True)
    embed.add_field(name="PPE Role", value=ppe_role_text, inline=True)
    embed.add_field(name="PPE Count", value=f"{len(player_data.ppes)}/{max_ppes}", inline=True)
    embed.add_field(name="Team", value=player_data.team_name or "N/A", inline=True)
    embed.add_field(name="Best PPE", value=best_line, inline=False)
    embed.add_field(name="Active PPE", value=active_line, inline=False)
    embed.add_field(name="Season Items", value=str(len(player_data.unique_items)), inline=True)
    embed.set_footer(text="Use buttons below to manage player data, roles, and loot views.")
    return embed


def add_to_contest_embed(target: ManagedPlayerTarget) -> discord.Embed:
    embed = discord.Embed(
        title=f"Manage Player - {target.display_name}",
        description=(
            "This user does not currently have the PPE Player role.\n"
            "Use Add To Contest to give the role and enable standard PPE player commands."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="Discord ID", value=str(target.user_id), inline=True)
    embed.add_field(name="Current Status", value="Not in contest", inline=True)
    return embed


def active_ppe_for_player(player_data: PlayerData) -> PPEData | None:
    for ppe in player_data.ppes:
        if int(ppe.id) == int(player_data.active_ppe or -1):
            return ppe
    return None


async def send_target_ppe_list_markdown_followup(
    interaction: discord.Interaction,
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
) -> None:
    temp_file_path = ""
    try:
        guild_config = await load_guild_config(interaction)
        temp_file_path = create_ppe_list_markdown_file(
            player_data,
            display_name=target.display_name,
            include_best_marker=False,
            guild_config=guild_config,
        )
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_target_season_loot_markdown_followup(
    interaction: discord.Interaction,
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
) -> None:
    items_list = sorted(player_data.unique_items, key=lambda x: (x[0].lower(), x[1]))

    if not items_list:
        await interaction.followup.send(f"{target.display_name} has no season loot tracked yet.", ephemeral=True)
        return

    temp_file_path = create_season_loot_markdown_file(
        player_data.unique_items,
        display_name=target.display_name,
    )
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def send_target_loot_markdown_followup(interaction: discord.Interaction, *, ppe: PPEData) -> None:
    from utils.loot_table_md_builder import create_loot_markdown_file

    guild_config = await load_guild_config(interaction)
    temp_file_path = create_loot_markdown_file(ppe, guild_config=guild_config)
    try:
        await interaction.followup.send(file=discord.File(temp_file_path), ephemeral=True)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def character_embed_for_target(
    *,
    target: ManagedPlayerTarget,
    player_data: PlayerData,
    ppe: PPEData,
    index: int,
    total: int,
    is_active: bool,
    is_best: bool,
    is_realmshark_connected: bool,
    guild_config: dict | None,
) -> discord.Embed:
    proxy_user = target.member if target.member is not None else discord.Object(id=target.user_id)
    embed = build_character_embed(
        user=proxy_user,
        player_data=player_data,
        ppe=ppe,
        index=index,
        total=total,
        is_active=is_active,
        is_best=is_best,
        is_realmshark_connected=is_realmshark_connected,
        guild_config=guild_config,
    )
    embed.description = f"{target.display_name}'s Character Panel\nCharacter {index}/{total}"
    return embed


async def realmshark_connected_ppe_ids(interaction: discord.Interaction, user_id: int) -> set[int]:
    from menus.myinfo.common import realmshark_connected_ppe_ids as myinfo_connected_ids

    return await myinfo_connected_ids(interaction, user_id)


__all__ = [
    "ManagedPlayerTarget",
    "active_ppe_for_player",
    "character_embed_for_target",
    "close_manageplayer_menu",
    "penalty_input_defaults",
    "realmshark_connected_ppe_ids",
    "send_followup_text",
    "send_target_loot_markdown_followup",
    "send_target_ppe_list_markdown_followup",
    "send_target_season_loot_markdown_followup",
    "target_home_embed",
    "add_to_contest_embed",
]
