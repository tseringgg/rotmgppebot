import discord

from menus.sniffer import open_managesniffer_menu


async def command(interaction: discord.Interaction) -> None:
    await open_managesniffer_menu(interaction)
