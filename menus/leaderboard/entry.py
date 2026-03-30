from __future__ import annotations

import discord

from menus.leaderboard.services import require_guild
from menus.leaderboard.views import LeaderboardHomeView
from utils.guild_config import get_contest_settings


async def open_leaderboard_menu(interaction: discord.Interaction) -> None:
    if await require_guild(interaction) is None:
        return

    contest_settings = await get_contest_settings(interaction)
    view = LeaderboardHomeView(owner_id=interaction.user.id, contest_settings=contest_settings)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
