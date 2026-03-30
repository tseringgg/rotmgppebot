"""Validation and parsing helpers for /managesniffer interactions."""

from __future__ import annotations

import discord
from menus.menu_utils.lookup_parsing import parse_channel_id, parse_user_id, resolve_member_from_input


def resolve_member(guild: discord.Guild | None, user_id: int) -> discord.Member | None:
    if guild is None:
        return None
    return guild.get_member(int(user_id))

