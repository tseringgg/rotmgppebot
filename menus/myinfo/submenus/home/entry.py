"""Home submenu entrypoint for /myinfo."""

from __future__ import annotations

import discord

from menus.myinfo.entry import open_myinfo_home


async def open_home(interaction: discord.Interaction, *, max_ppes: int) -> None:
    await open_myinfo_home(interaction, max_ppes=max_ppes)


__all__ = ["open_home"]
