"""Validation and parsing helpers for /managesniffer interactions."""

from __future__ import annotations

import re

import discord


def resolve_member(guild: discord.Guild | None, user_id: int) -> discord.Member | None:
    if guild is None:
        return None
    return guild.get_member(int(user_id))


def parse_user_id(raw: str) -> int | None:
    text = str(raw or "").strip()
    if text.startswith("<@") and text.endswith(">"):
        text = text[2:-1].replace("!", "")

    if not text.isdigit():
        return None

    value = int(text)
    return value if value > 0 else None


def resolve_member_from_input(guild: discord.Guild, raw_value: str) -> discord.Member | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    mention_match = re.fullmatch(r"<@!?(\d+)>", text)
    if mention_match:
        member = guild.get_member(int(mention_match.group(1)))
        if member is not None:
            return member

    if text.isdigit():
        member = guild.get_member(int(text))
        if member is not None:
            return member

    lowered = text.casefold()
    for member in guild.members:
        if member.display_name.casefold() == lowered or member.name.casefold() == lowered:
            return member

    return None


def parse_channel_id(raw: str) -> int | None:
    text = str(raw or "").strip()
    if text.startswith("<#") and text.endswith(">"):
        text = text[2:-1]

    if not text.isdigit():
        return None

    value = int(text)
    return value if value > 0 else None
