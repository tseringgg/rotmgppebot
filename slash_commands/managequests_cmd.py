from __future__ import annotations

import discord

from menus.managequests import open_managequests_menu


async def command(interaction: discord.Interaction):
    await open_managequests_menu(interaction)
