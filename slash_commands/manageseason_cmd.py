from __future__ import annotations

import discord

from menus.manageseason import open_manageseason_menu


async def command(interaction: discord.Interaction) -> None:
    await open_manageseason_menu(interaction)
