"""Business logic for /manageseason picture suggestions submenu."""

from __future__ import annotations

from typing import Any

import discord

from utils.settings.channel_settings import (
    clear_item_suggestions_enabled_channels,
    get_item_suggestions_mode_enabled,
    list_item_suggestions_enabled_channels,
    set_item_suggestions_enabled_for_channels,
    set_item_suggestions_mode_enabled,
)


def _normalize_positive_int_channel_ids(channel_ids: list[str]) -> list[int]:
    normalized: list[int] = []
    for raw_channel_id in channel_ids:
        try:
            parsed = int(str(raw_channel_id).strip())
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            normalized.append(parsed)

    return sorted(set(normalized))


def _classify_channel_ids(
    guild: discord.Guild,
    channel_ids: list[int],
) -> tuple[list[int], list[int], list[int]]:
    valid_text_channel_ids: list[int] = []
    non_text_channel_ids: list[int] = []
    missing_channel_ids: list[int] = []

    for channel_id in sorted(set(channel_ids)):
        channel = guild.get_channel(channel_id)
        if channel is None:
            missing_channel_ids.append(channel_id)
            continue

        if isinstance(channel, discord.TextChannel):
            valid_text_channel_ids.append(channel_id)
        else:
            non_text_channel_ids.append(channel_id)

    return valid_text_channel_ids, non_text_channel_ids, missing_channel_ids


async def load_picture_suggestions_state(*, guild: discord.Guild | None) -> dict[str, Any]:
    """Load mode status and currently enabled channels for rendering."""
    if guild is None:
        raise ValueError("This action can only be used in a server.")

    guild_id = str(guild.id)
    mode_enabled = await get_item_suggestions_mode_enabled(guild_id)
    raw_enabled_ids = await list_item_suggestions_enabled_channels(guild_id)

    normalized_ids = _normalize_positive_int_channel_ids(raw_enabled_ids)
    valid_text_channel_ids, non_text_channel_ids, missing_channel_ids = _classify_channel_ids(guild, normalized_ids)

    return {
        "enabled": bool(mode_enabled),
        "enabled_channel_ids": valid_text_channel_ids,
        "missing_channel_ids": missing_channel_ids,
        "non_text_channel_ids": non_text_channel_ids,
    }


async def enable_picture_suggestions(*, guild: discord.Guild | None) -> None:
    """Enable picture suggestions mode for this guild."""
    if guild is None:
        raise ValueError("This action can only be used in a server.")

    await set_item_suggestions_mode_enabled(str(guild.id), True)


async def disable_picture_suggestions(*, guild: discord.Guild | None) -> int:
    """Disable picture suggestions mode and clear all enabled channels."""
    if guild is None:
        raise ValueError("This action can only be used in a server.")

    cleared = await clear_item_suggestions_enabled_channels(str(guild.id))
    await set_item_suggestions_mode_enabled(str(guild.id), False)
    return cleared


async def add_picture_suggestion_channels(
    *,
    guild: discord.Guild | None,
    channel_ids: list[int],
) -> dict[str, Any]:
    """Enable item suggestions for selected channels with validation feedback."""
    if guild is None:
        raise ValueError("This action can only be used in a server.")

    valid_text_channel_ids, non_text_channel_ids, missing_channel_ids = _classify_channel_ids(guild, channel_ids)

    current_state = await load_picture_suggestions_state(guild=guild)
    currently_enabled = set(current_state["enabled_channel_ids"])

    added_channel_ids = sorted(channel_id for channel_id in valid_text_channel_ids if channel_id not in currently_enabled)
    already_enabled_ids = sorted(channel_id for channel_id in valid_text_channel_ids if channel_id in currently_enabled)

    if added_channel_ids:
        await set_item_suggestions_enabled_for_channels(
            str(guild.id),
            [str(channel_id) for channel_id in added_channel_ids],
            enabled=True,
        )

    await set_item_suggestions_mode_enabled(str(guild.id), True)
    refreshed_state = await load_picture_suggestions_state(guild=guild)

    return {
        "added_channel_ids": added_channel_ids,
        "already_enabled_ids": already_enabled_ids,
        "non_text_channel_ids": non_text_channel_ids,
        "missing_channel_ids": missing_channel_ids,
        "state": refreshed_state,
    }


async def remove_picture_suggestion_channels(
    *,
    guild: discord.Guild | None,
    channel_ids: list[int],
) -> dict[str, Any]:
    """Disable item suggestions for selected channels with validation feedback."""
    if guild is None:
        raise ValueError("This action can only be used in a server.")

    valid_text_channel_ids, non_text_channel_ids, missing_channel_ids = _classify_channel_ids(guild, channel_ids)

    current_state = await load_picture_suggestions_state(guild=guild)
    currently_enabled = set(current_state["enabled_channel_ids"])

    removed_channel_ids = sorted(channel_id for channel_id in valid_text_channel_ids if channel_id in currently_enabled)
    not_enabled_ids = sorted(channel_id for channel_id in valid_text_channel_ids if channel_id not in currently_enabled)

    if removed_channel_ids:
        await set_item_suggestions_enabled_for_channels(
            str(guild.id),
            [str(channel_id) for channel_id in removed_channel_ids],
            enabled=False,
        )

    refreshed_state = await load_picture_suggestions_state(guild=guild)

    return {
        "removed_channel_ids": removed_channel_ids,
        "not_enabled_ids": not_enabled_ids,
        "non_text_channel_ids": non_text_channel_ids,
        "missing_channel_ids": missing_channel_ids,
        "state": refreshed_state,
    }
