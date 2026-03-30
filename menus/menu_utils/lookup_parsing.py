"""Reusable parsing and member lookup helpers for menu input fields.

These helpers are intentionally lightweight so menu modules can share a
single parsing behavior for mention/id text fields.
"""

from __future__ import annotations

import re

import discord


def parse_user_id(raw: str) -> int | None:
    text = str(raw or "").strip()
    mention_match = re.fullmatch(r"<@!?(\d+)>", text)
    if mention_match:
        text = mention_match.group(1)

    if not text.isdigit():
        return None

    value = int(text)
    return value if value > 0 else None


def parse_channel_id(raw: str) -> int | None:
    text = str(raw or "").strip()
    mention_match = re.fullmatch(r"<#(\d+)>", text)
    if mention_match:
        text = mention_match.group(1)

    if not text.isdigit():
        return None

    value = int(text)
    return value if value > 0 else None


def resolve_member_from_input(guild: discord.Guild, raw_value: str) -> discord.Member | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    parsed_id = parse_user_id(text)
    if parsed_id is not None:
        member = guild.get_member(parsed_id)
        if member is not None:
            return member

    lowered = text.casefold()
    for member in guild.members:
        if member.display_name.casefold() == lowered or member.name.casefold() == lowered:
            return member

    return None


__all__ = ["parse_channel_id", "parse_user_id", "resolve_member_from_input"]
