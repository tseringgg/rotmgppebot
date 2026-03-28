from __future__ import annotations

import discord

from menus.leaderboard.views import LeaderboardHomeView


async def open_leaderboard_menu(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    view = LeaderboardHomeView(owner_id=interaction.user.id)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
