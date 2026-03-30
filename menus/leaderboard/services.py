"""Service helpers for leaderboard command handlers."""

from __future__ import annotations

import discord

from menus.leaderboard.common import send_error_response


async def require_guild(interaction: discord.Interaction) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await send_error_response(interaction, "❌ This command can only be used in a server.")
        return None
    return guild


def member_display_name(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(int(user_id))
    if member is None:
        return f"Unknown User ({user_id})"
    return member.display_name


__all__ = ["member_display_name", "require_guild"]
