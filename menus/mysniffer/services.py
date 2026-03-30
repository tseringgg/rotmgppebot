"""Service helpers for player-facing /mysniffer flows."""

from __future__ import annotations

from typing import Any

import discord

from menus.menu_utils.sniffer_shared import (
    generate_link_token_for_user,
    iter_user_links,
    load_sniffer_settings,
    revoke_token,
)


async def load_user_sniffer_state(
    interaction: discord.Interaction,
    *,
    user_id: int,
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    settings, links = await load_sniffer_settings(interaction)
    return settings, iter_user_links(links, user_id)


async def generate_user_link_token(interaction: discord.Interaction, *, user_id: int) -> str:
    return await generate_link_token_for_user(interaction, user_id)


async def revoke_user_token(interaction: discord.Interaction, *, token: str) -> bool:
    return await revoke_token(interaction, token)


__all__ = [
    "generate_user_link_token",
    "load_sniffer_settings",
    "load_user_sniffer_state",
    "revoke_user_token",
]
