"""Home submenu entrypoint for /manageplayer."""

from __future__ import annotations

import discord

from menus.manageplayer.entry import open_manageplayer_home
from menus.manageplayer.targets import ManagedPlayerTarget


async def open_home(
    interaction: discord.Interaction,
    *,
    owner_id: int,
    target: ManagedPlayerTarget,
    max_ppes: int,
) -> None:
    await open_manageplayer_home(interaction, owner_id=owner_id, target=target, max_ppes=max_ppes)


__all__ = ["open_home"]
