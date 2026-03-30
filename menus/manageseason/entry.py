"""Entry helpers for opening /manageseason interactive panels."""

from __future__ import annotations

import discord

from menus.manageseason.submenus.home.views import ManageSeasonHomeView


async def open_manageseason_menu(interaction: discord.Interaction) -> None:
    """Open the top-level season administration menu."""
    if not interaction.guild:
        await interaction.response.send_message("ERROR: This command can only be used in a server.", ephemeral=True)
        return

    view = ManageSeasonHomeView(owner_id=interaction.user.id)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
