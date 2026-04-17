"""Entrypoints for bot-cost submenu in /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.services import load_bot_cost_summary_for_menu
from menus.manageseason.submenus.cost.views import ManageBotCostView


async def open_manage_bot_cost_menu(interaction: discord.Interaction, *, owner_id: int) -> None:
    """Render the bot-cost panel into the active /manageseason message."""
    summary = await load_bot_cost_summary_for_menu(interaction, window_hours=24, top_n=10)
    view = ManageBotCostView(owner_id=owner_id, summary=summary, window_hours=24)
    await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = ["open_manage_bot_cost_menu"]
