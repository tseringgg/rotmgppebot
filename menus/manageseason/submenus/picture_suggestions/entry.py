"""Entrypoints for picture suggestions submenu in /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.submenus.picture_suggestions.views import build_picture_suggestions_panel


async def open_picture_suggestions_menu(interaction: discord.Interaction, *, owner_id: int) -> None:
    """Render the picture suggestions menu panel into the active message."""
    embed, view = await build_picture_suggestions_panel(guild=interaction.guild, owner_id=owner_id)
    await interaction.response.edit_message(embed=embed, view=view)


__all__ = ["open_picture_suggestions_menu"]
