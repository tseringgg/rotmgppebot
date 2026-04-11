"""Entrypoints for opening /myinfo menu screens."""

from __future__ import annotations

import discord

from menus.myinfo.common import build_home_embed, refresh_player_data
from utils.guild_config import get_max_ppes


async def open_myinfo_home(interaction: discord.Interaction, *, max_ppes: int) -> None:
    from menus.myinfo.submenus.home.views import MyInfoHomeView

    player_data = await refresh_player_data(interaction, interaction.user.id)

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

    player_data = await refresh_player_data(interaction, interaction.user.id)
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