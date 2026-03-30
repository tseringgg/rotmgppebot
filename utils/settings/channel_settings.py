"""Guild channel-level settings helpers (item suggestions, etc.)."""

from __future__ import annotations

import asyncio
import os

from utils.player_records import DATA_DIR, _read_json_file, _write_atomic_json, get_lock


def get_guild_settings_path(guild_id: int | str) -> str:
    """Return the file path for this guild's channel settings file."""
    return os.path.join(DATA_DIR, f"{guild_id}_channel_settings.json")


async def get_item_suggestions_enabled(guild_id: str, channel_id: str) -> bool:
    """Return True if item suggestions are enabled for the given channel."""
    guild_id = str(guild_id)
    channel_id = str(channel_id)
    path = get_guild_settings_path(guild_id)

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

    enabled = (
        data
        .get("channels", {})
        .get(channel_id, {})
        .get("item_suggestions_enabled", False)
    )
    print(f"[settings] get_item_suggestions_enabled guild={guild_id} channel={channel_id} -> {enabled}")
    return bool(enabled)


async def set_item_suggestions_enabled(guild_id: str, channel_id: str, enabled: bool):
    """Set whether item suggestions are enabled for the given channel and persist the change."""
    guild_id = str(guild_id)
    channel_id = str(channel_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

        channels = data.setdefault("channels", {})
        channel_entry = channels.setdefault(channel_id, {})
        channel_entry["item_suggestions_enabled"] = enabled

        print(f"[settings] set_item_suggestions_enabled guild={guild_id} channel={channel_id} -> {enabled}")
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)


async def toggle_item_suggestions(guild_id: str, channel_id: str) -> bool:
    """Flip the item suggestions setting for the given channel and return the new value."""
    guild_id = str(guild_id)
    channel_id = str(channel_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

        channels = data.setdefault("channels", {})
        channel_entry = channels.setdefault(channel_id, {})

        current = bool(channel_entry.get("item_suggestions_enabled", False))
        new_value = not current
        channel_entry["item_suggestions_enabled"] = new_value

        print(f"[settings] toggle_item_suggestions guild={guild_id} channel={channel_id} -> {new_value}")
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    return new_value


async def get_item_suggestions_mode_enabled(guild_id: str) -> bool:
    """Return whether picture suggestion mode is enabled for this guild."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

    enabled = bool(data.get("item_suggestions_enabled", False))
    print(f"[settings] get_item_suggestions_mode_enabled guild={guild_id} -> {enabled}")
    return enabled


async def set_item_suggestions_mode_enabled(guild_id: str, enabled: bool):
    """Set whether picture suggestion mode is enabled for this guild."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)
        data["item_suggestions_enabled"] = bool(enabled)

        print(f"[settings] set_item_suggestions_mode_enabled guild={guild_id} -> {bool(enabled)}")
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)


async def list_item_suggestions_enabled_channels(guild_id: str) -> list[str]:
    """Return channel IDs with item suggestions currently enabled."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

    channels = data.get("channels", {})
    if not isinstance(channels, dict):
        return []

    enabled_channel_ids: list[str] = []
    for channel_id, raw_entry in channels.items():
        if not isinstance(raw_entry, dict):
            continue
        if bool(raw_entry.get("item_suggestions_enabled", False)):
            enabled_channel_ids.append(str(channel_id))

    return enabled_channel_ids


async def set_item_suggestions_enabled_for_channels(
    guild_id: str,
    channel_ids: list[str],
    *,
    enabled: bool,
) -> None:
    """Set item suggestions enabled/disabled for multiple channels at once."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    normalized_ids = [str(channel_id).strip() for channel_id in channel_ids if str(channel_id).strip()]
    if not normalized_ids:
        return

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)
        channels = data.setdefault("channels", {})

        for channel_id in normalized_ids:
            channel_entry = channels.setdefault(channel_id, {})
            channel_entry["item_suggestions_enabled"] = bool(enabled)

        if enabled:
            data["item_suggestions_enabled"] = True

        print(
            f"[settings] set_item_suggestions_enabled_for_channels guild={guild_id} "
            f"count={len(normalized_ids)} -> {bool(enabled)}"
        )
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)


async def clear_item_suggestions_enabled_channels(guild_id: str) -> int:
    """Disable item suggestions for all channels and return number of channels cleared."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)
        channels = data.get("channels", {})

        cleared = 0
        if isinstance(channels, dict):
            for channel_entry in channels.values():
                if not isinstance(channel_entry, dict):
                    continue
                if bool(channel_entry.get("item_suggestions_enabled", False)):
                    cleared += 1
                channel_entry["item_suggestions_enabled"] = False

        data["item_suggestions_enabled"] = False
        print(f"[settings] clear_item_suggestions_enabled_channels guild={guild_id} cleared={cleared}")
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    return cleared
