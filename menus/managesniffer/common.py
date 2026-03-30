"""Embed builders for /managesniffer views."""

from __future__ import annotations

from typing import Any

import discord

from menus.managesniffer.models import SnifferTokenRow
from menus.menu_utils.sniffer_shared import (
    configured_endpoint,
    iter_user_links,
    linked_character_counts,
    mention_for_channel,
    sniffer_connected_user_count,
    token_preview,
)
from menus.managesniffer.validators import resolve_member
from menus.mysniffer.common import build_mysniffer_home_embed


def build_managesniffer_home_embed(
    *,
    guild: discord.Guild | None,
    settings: dict[str, Any],
    links: dict[str, dict[str, Any]],
) -> discord.Embed:
    enabled = bool(settings.get("enabled", False))
    channel_id = int(settings.get("announce_channel_id", 0) or 0)
    endpoint = configured_endpoint(settings)
    connected_users = sniffer_connected_user_count(links)

    embed = discord.Embed(
        title="Manage Sniffer",
        description="Admin controls for sniffer integration and token management.",
        color=discord.Color.green() if enabled else discord.Color.orange(),
    )
    embed.add_field(name="Sniffer Enabled", value="Yes" if enabled else "No", inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(links)), inline=True)
    embed.add_field(name="Connected Players", value=str(connected_users), inline=True)
    embed.add_field(name="Output Channel", value=mention_for_channel(guild, channel_id), inline=False)
    embed.add_field(
        name="Endpoint",
        value=f"`{endpoint}`" if endpoint else "Not set. Players will see the generic endpoint setup hint.",
        inline=False,
    )

    if not enabled:
        embed.add_field(
            name="Enable Sniffer",
            value="Sniffer is disabled. Use **Enable Sniffer** to allow monitoring and ingest again.",
            inline=False,
        )
    else:
        embed.add_field(
            name="Admin Actions",
            value=(
                "Use the green buttons for day-to-day management. "
                "Use red buttons for destructive and lifecycle actions."
            ),
            inline=False,
        )

    embed.set_footer(text="This menu is admin-only.")
    return embed


def build_manage_player_sniffer_embed(
    *,
    guild_id: int | None,
    target_user: discord.abc.User,
    settings: dict[str, Any],
    links: dict[str, dict[str, Any]],
) -> discord.Embed:
    user_links = iter_user_links(links, target_user.id)
    mapped_count, seasonal_count = linked_character_counts(user_links)

    embed = build_mysniffer_home_embed(
        user=target_user,
        guild_id=guild_id,
        settings=settings,
        user_links=user_links,
    )
    embed.title = f"Manage Player Sniffer - {target_user.display_name}"
    embed.description = "Admin view of this player's /mysniffer dashboard."
    embed.add_field(name="Player ID", value=str(target_user.id), inline=True)
    embed.add_field(name="Player Mention", value=getattr(target_user, "mention", str(target_user.id)), inline=True)
    embed.add_field(name="Linked Tokens", value=str(len(user_links)), inline=True)
    embed.add_field(name="Mapped Characters", value=str(mapped_count), inline=True)
    embed.add_field(name="Seasonal Characters", value=str(seasonal_count), inline=True)
    embed.set_footer(text="Use these controls to manage this player's sniffer state.")
    return embed


def build_tokens_embed(
    *,
    guild: discord.Guild | None,
    page: int,
    per_page: int,
    token_entries: list[SnifferTokenRow],
) -> discord.Embed:
    total = len(token_entries)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    window = token_entries[start:end]

    embed = discord.Embed(
        title="Manage Sniffer Tokens",
        description="Review and revoke active sniffer link tokens.",
        color=discord.Color.blurple(),
    )

    if not window:
        embed.add_field(name="Tokens", value="No linked tokens found.", inline=False)
    else:
        lines: list[str] = []
        for row in window:
            owner_text = "unknown"
            if row.user_id is not None:
                owner_text = str(row.user_id)
                member = resolve_member(guild, row.user_id)
                if member is not None:
                    owner_text = f"{member.display_name} ({member.mention})"

            lines.append(
                f"- `{token_preview(row.token)}` | owner: {owner_text} | "
                f"created: `{row.created_at}` | last_used: `{row.last_used_at}`"
            )

        embed.add_field(name="Active Tokens", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Page {page + 1}/{total_pages} - total tokens: {total}")
    return embed
