"""Entrypoint helpers for /mysniffer and /managesniffer commands."""

from __future__ import annotations

import discord

from menus.sniffer.common import iter_user_links, load_sniffer_settings
from menus.sniffer.managesniffer_view import send_managesniffer_home
from menus.sniffer.mysniffer_view import MySnifferHomeView, build_mysniffer_home_embed


async def open_mysniffer_menu(interaction: discord.Interaction) -> None:
    settings, links = await load_sniffer_settings(interaction)
    user_links = iter_user_links(links, interaction.user.id)

    embed = build_mysniffer_home_embed(user=interaction.user, settings=settings, user_links=user_links)
    view = MySnifferHomeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_managesniffer_menu(interaction: discord.Interaction) -> None:
    await send_managesniffer_home(interaction)
