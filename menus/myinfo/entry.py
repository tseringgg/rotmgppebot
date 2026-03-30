"""Entrypoints for opening /myinfo menu screens."""

from __future__ import annotations

import discord

from menus.myinfo.common import build_home_embed
from utils.guild_config import get_max_ppes
from utils.player_records import ensure_player_exists, load_player_records


async def open_myinfo_home(interaction: discord.Interaction, *, max_ppes: int) -> None:
    from menus.myinfo.submenus.home.views import MyInfoHomeView

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]

    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break

    embed = build_home_embed(interaction.user, player_data, active_ppe, max_ppes=max_ppes)
    view = MyInfoHomeView(interaction.user.id, max_ppes=max_ppes)
    await interaction.response.edit_message(embed=embed, view=view)


async def open_myinfo_menu(interaction: discord.Interaction) -> None:
    """Open the /myinfo dashboard entry menu for the invoking user."""

    from menus.myinfo.submenus.home.views import MyInfoHomeView

    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    max_ppes = await get_max_ppes(interaction)

    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break

    embed = build_home_embed(interaction.user, player_data, active_ppe, max_ppes=max_ppes)
    view = MyInfoHomeView(interaction.user.id, max_ppes=max_ppes)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


__all__ = ["open_myinfo_home", "open_myinfo_menu"]