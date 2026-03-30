"""Entry helpers for opening /managequests interactive panels."""

from __future__ import annotations

import discord

from menus.managequests.common import load_managequests_settings
from menus.managequests.submenus.home.views import ManageQuestsHomeView


async def open_managequests_menu(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    settings = await load_managequests_settings(interaction)
    view = ManageQuestsHomeView(owner_id=interaction.user.id, settings=settings)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
