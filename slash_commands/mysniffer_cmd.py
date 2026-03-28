import discord

from menus.sniffer import open_mysniffer_menu


async def command(interaction: discord.Interaction) -> None:
    await open_mysniffer_menu(interaction)
