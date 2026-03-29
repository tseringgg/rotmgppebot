from __future__ import annotations

import discord

from menus.leaderboard.views import LeaderboardHomeView
from utils.guild_config import get_contest_settings


async def open_leaderboard_menu(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    contest_settings = await get_contest_settings(interaction)
    view = LeaderboardHomeView(owner_id=interaction.user.id, contest_settings=contest_settings)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
