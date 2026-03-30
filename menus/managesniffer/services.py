"""Service helpers for /managesniffer views."""

from __future__ import annotations

import discord

from menus.managesniffer.models import SnifferTokenRow
from menus.menu_utils.sniffer_shared import (
    generate_link_token_for_user,
    load_sniffer_settings,
    reset_all_sniffer_settings,
    reset_output_channel,
    revoke_all_tokens_for_user,
    revoke_token,
    set_endpoint,
    set_output_channel,
    set_sniffer_enabled,
)


async def load_token_entries(interaction: discord.Interaction) -> list[SnifferTokenRow]:
    _settings, links = await load_sniffer_settings(interaction)
    rows = [SnifferTokenRow.from_link(token, link_data) for token, link_data in links.items()]
    return sorted(rows, key=lambda row: row.token)


__all__ = [
    "generate_link_token_for_user",
    "load_sniffer_settings",
    "load_token_entries",
    "reset_all_sniffer_settings",
    "reset_output_channel",
    "revoke_all_tokens_for_user",
    "revoke_token",
    "set_endpoint",
    "set_output_channel",
    "set_sniffer_enabled",
]
