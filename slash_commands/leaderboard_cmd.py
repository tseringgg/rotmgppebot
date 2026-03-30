import discord

from menus.leaderboard import open_leaderboard_menu


async def command(interaction: discord.Interaction) -> None:
    await open_leaderboard_menu(interaction)
