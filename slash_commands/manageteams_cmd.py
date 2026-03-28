import discord

from menus.manageteams import open_manage_teams_menu


async def command(interaction: discord.Interaction) -> None:
    await open_manage_teams_menu(interaction)
