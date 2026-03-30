"""Contest leaderboard dispatcher for the /leaderboard menu."""

from __future__ import annotations

from typing import Awaitable, Callable

import discord

from menus.leaderboard.common import send_error_response
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
        await send_error_response(interaction, "❌ Invalid contest leaderboard type configured.")
        return

    handler = _CONTEST_HANDLERS.get(normalized)
    if handler is None:
        await send_error_response(interaction, "❌ Contest leaderboard handler is unavailable.")
        return

    await handler(interaction)


async def run_default_contest_leaderboard(interaction: discord.Interaction) -> None:
    """Run the guild's default contest leaderboard (if configured)."""
    contest_settings = await get_contest_settings(interaction)
    default_leaderboard = normalize_contest_leaderboard_id(contest_settings.get("default_contest_leaderboard"))
    if default_leaderboard is None:
        await send_error_response(
            interaction,
            "❌ A default contest leaderboard has not been set yet.\n"
            "Ask an admin to use `/manageseason` → **Manage Contests** → **Set Contest Type**.",
        )
        return

    await run_contest_leaderboard(interaction, default_leaderboard)
