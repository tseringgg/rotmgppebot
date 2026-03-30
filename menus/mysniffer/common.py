"""Embed builders and pure helpers for /mysniffer."""

from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils.sniffer_shared import (
    build_setup_steps,
    configured_endpoint,
    linked_character_counts,
    token_preview,
)


def build_mysniffer_home_embed(
    *,
    user: discord.abc.User,
    guild_id: int | None,
    settings: dict[str, Any],
    user_links: list[tuple[str, dict[str, Any]]],
) -> discord.Embed:
    enabled = bool(settings.get("enabled", False))
    mapped_count, seasonal_count = linked_character_counts(user_links)

    embed = discord.Embed(
        title=f"My Sniffer - {user.display_name}",
        description="Manage your sniffer connection and character routing.",
        color=discord.Color.teal() if enabled else discord.Color.orange(),
    )

    embed.add_field(name="Sniffer Enabled", value="Yes" if enabled else "No", inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(user_links)), inline=True)
    embed.add_field(name="Mapped Characters", value=str(mapped_count), inline=True)
    embed.add_field(name="Seasonal Characters", value=str(seasonal_count), inline=True)

    if enabled:
        embed.add_field(
            name="Setup Steps",
            value=build_setup_steps(guild_id, configured_endpoint(settings)),
            inline=False,
        )
    else:
        embed.add_field(
            name="Status",
            value="Sniffer is currently disabled on this server. Ask a PPE Admin to enable it in `/managesniffer`.",
            inline=False,
        )

    if user_links:
        token_lines = [f"- `{token_preview(token)}`" for token, _ in user_links[:10]]
        embed.add_field(name="Your Active Tokens", value="\n".join(token_lines), inline=False)

    embed.set_footer(text="Use the buttons below to generate, unlink, or configure your sniffer.")
    return embed


__all__ = ["build_mysniffer_home_embed"]
