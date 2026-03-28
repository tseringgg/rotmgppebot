import discord

from menus.myinfo import open_myinfo_menu


async def command(interaction: discord.Interaction) -> None:
    await open_myinfo_menu(interaction)
