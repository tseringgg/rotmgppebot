"""Entrypoints for /managesniffer menu flow."""

from __future__ import annotations

import discord

from menus.managesniffer.submenus.home.views import send_managesniffer_home


async def open_managesniffer_menu(interaction: discord.Interaction) -> None:
    await send_managesniffer_home(interaction)


__all__ = ["open_managesniffer_menu"]
