"""Contest leaderboard dispatcher for the /leaderboard menu."""

from __future__ import annotations

from typing import Awaitable, Callable

import discord

from utils.contest_leaderboards import normalize_contest_leaderboard_id
from utils.guild_config import get_contest_settings

from . import ppeleaderboard, questleaderboard, seasonleaderboard, teamleaderboard


_ContestHandler = Callable[[discord.Interaction], Awaitable[None]]

_CONTEST_HANDLERS: dict[str, _ContestHandler] = {
    "ppe": ppeleaderboard.command,
    "quest": questleaderboard.command,
    "season": seasonleaderboard.command,
    "team": teamleaderboard.command,
}


async def run_contest_leaderboard(interaction: discord.Interaction, leaderboard_id: str) -> None:
    """Run one contest leaderboard by normalized identifier."""
    normalized = normalize_contest_leaderboard_id(leaderboard_id)
    if normalized is None:
        await interaction.response.send_message("❌ Invalid contest leaderboard type configured.", ephemeral=True)
        return

    handler = _CONTEST_HANDLERS.get(normalized)
    if handler is None:
        await interaction.response.send_message("❌ Contest leaderboard handler is unavailable.", ephemeral=True)
        return

    await handler(interaction)


async def run_default_contest_leaderboard(interaction: discord.Interaction) -> None:
    """Run the guild's default contest leaderboard (if configured)."""
    contest_settings = await get_contest_settings(interaction)
    default_leaderboard = normalize_contest_leaderboard_id(contest_settings.get("default_contest_leaderboard"))
    if default_leaderboard is None:
        await interaction.response.send_message(
            "❌ A default contest leaderboard has not been set yet.\n"
            "Ask an admin to use `/manageseason` → **Manage Contests** → **Set Contest Type**.",
            ephemeral=True,
        )
        return

    await run_contest_leaderboard(interaction, default_leaderboard)
