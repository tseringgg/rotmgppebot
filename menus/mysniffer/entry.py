"""Entrypoints for /mysniffer menu flow."""

from __future__ import annotations

import discord

from menus.mysniffer.common import build_mysniffer_home_embed
from menus.mysniffer.services import load_user_sniffer_state
from menus.mysniffer.views import MySnifferHomeView


async def open_mysniffer_menu(interaction: discord.Interaction) -> None:
    settings, user_links = await load_user_sniffer_state(interaction, user_id=interaction.user.id)

    embed = build_mysniffer_home_embed(
        user=interaction.user,
        guild_id=interaction.guild.id if interaction.guild else None,
        settings=settings,
        user_links=user_links,
    )
    view = MySnifferHomeView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


__all__ = ["open_mysniffer_menu"]
