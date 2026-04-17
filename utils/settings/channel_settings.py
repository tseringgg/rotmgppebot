"""Guild channel-level settings helpers (item suggestions, etc.)."""

from __future__ import annotations

import asyncio
import os
import time

from utils.player_records import DATA_DIR, _read_json_file, _write_atomic_json, get_lock


_SETTINGS_CACHE_TTL_SECONDS = 30.0
_CHANNEL_ENABLED_CACHE: dict[tuple[str, str], tuple[bool, float]] = {}
_MODE_ENABLED_CACHE: dict[str, tuple[bool, float]] = {}
_CHANNEL_CACHE_MAX_ENTRIES = 20000
_MODE_CACHE_MAX_ENTRIES = 5000
_CHANNEL_CACHE_PRUNE_EVERY = 128
_MODE_CACHE_PRUNE_EVERY = 64
_channel_cache_op_count = 0
_mode_cache_op_count = 0


def _prune_channel_enabled_cache(now: float | None = None) -> None:
    now_monotonic = time.monotonic() if now is None else now
    expired_keys = [
        key
        for key, (_enabled, expires_at) in _CHANNEL_ENABLED_CACHE.items()
        if now_monotonic > expires_at
    ]
    for key in expired_keys:
        _CHANNEL_ENABLED_CACHE.pop(key, None)

    overflow = len(_CHANNEL_ENABLED_CACHE) - _CHANNEL_CACHE_MAX_ENTRIES
    if overflow > 0:
        # Drop oldest-to-expire entries first when above cap.
        keys_by_expiry = sorted(_CHANNEL_ENABLED_CACHE.items(), key=lambda entry: entry[1][1])
        for key, _value in keys_by_expiry[:overflow]:
            _CHANNEL_ENABLED_CACHE.pop(key, None)


def _maybe_prune_channel_enabled_cache() -> None:
    global _channel_cache_op_count
    _channel_cache_op_count += 1
    if _channel_cache_op_count % _CHANNEL_CACHE_PRUNE_EVERY == 0:
        _prune_channel_enabled_cache()


def _prune_mode_enabled_cache(now: float | None = None) -> None:
    now_monotonic = time.monotonic() if now is None else now
    expired_keys = [
        key
        for key, (_enabled, expires_at) in _MODE_ENABLED_CACHE.items()
        if now_monotonic > expires_at
    ]
    for key in expired_keys:
        _MODE_ENABLED_CACHE.pop(key, None)

    overflow = len(_MODE_ENABLED_CACHE) - _MODE_CACHE_MAX_ENTRIES
    if overflow > 0:
        keys_by_expiry = sorted(_MODE_ENABLED_CACHE.items(), key=lambda entry: entry[1][1])
        for key, _value in keys_by_expiry[:overflow]:
            _MODE_ENABLED_CACHE.pop(key, None)


def _maybe_prune_mode_enabled_cache() -> None:
    global _mode_cache_op_count
    _mode_cache_op_count += 1
    if _mode_cache_op_count % _MODE_CACHE_PRUNE_EVERY == 0:
        _prune_mode_enabled_cache()


def _read_cached_channel_enabled(guild_id: str, channel_id: str) -> bool | None:
    _maybe_prune_channel_enabled_cache()

    cached = _CHANNEL_ENABLED_CACHE.get((guild_id, channel_id))
    if cached is None:
        return None

    enabled, expires_at = cached
    if time.monotonic() > expires_at:
        _CHANNEL_ENABLED_CACHE.pop((guild_id, channel_id), None)
        return None
    return enabled


def _write_cached_channel_enabled(guild_id: str, channel_id: str, enabled: bool) -> None:
    _maybe_prune_channel_enabled_cache()
    _CHANNEL_ENABLED_CACHE[(guild_id, channel_id)] = (
        bool(enabled),
        time.monotonic() + _SETTINGS_CACHE_TTL_SECONDS,
    )


def _clear_cached_channels_for_guild(guild_id: str) -> None:
    keys_to_drop = [key for key in _CHANNEL_ENABLED_CACHE if key[0] == guild_id]
    for key in keys_to_drop:
        _CHANNEL_ENABLED_CACHE.pop(key, None)


def _read_cached_mode_enabled(guild_id: str) -> bool | None:
    _maybe_prune_mode_enabled_cache()

    cached = _MODE_ENABLED_CACHE.get(guild_id)
    if cached is None:
        return None

    enabled, expires_at = cached
    if time.monotonic() > expires_at:
        _MODE_ENABLED_CACHE.pop(guild_id, None)
        return None
    return enabled


def _write_cached_mode_enabled(guild_id: str, enabled: bool) -> None:
    _maybe_prune_mode_enabled_cache()
    _MODE_ENABLED_CACHE[guild_id] = (
        bool(enabled),
        time.monotonic() + _SETTINGS_CACHE_TTL_SECONDS,
    )


def clear_guild_cache(guild_id: int | str) -> None:
    guild_key = str(guild_id)
    _clear_cached_channels_for_guild(guild_key)
    _MODE_ENABLED_CACHE.pop(guild_key, None)


def get_cache_sizes() -> dict[str, int]:
    return {
        "channel_enabled": len(_CHANNEL_ENABLED_CACHE),
        "mode_enabled": len(_MODE_ENABLED_CACHE),
    }


def get_guild_settings_path(guild_id: int | str) -> str:
    """Return the file path for this guild's channel settings file."""
    return os.path.join(DATA_DIR, f"{guild_id}_channel_settings.json")


async def get_item_suggestions_enabled(guild_id: str, channel_id: str) -> bool:
    """Return True if item suggestions are enabled for the given channel."""
    guild_id = str(guild_id)
    channel_id = str(channel_id)

    cached_enabled = _read_cached_channel_enabled(guild_id, channel_id)
    if cached_enabled is not None:
        return cached_enabled

    path = get_guild_settings_path(guild_id)

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

    enabled = (
        data
        .get("channels", {})
        .get(channel_id, {})
        .get("item_suggestions_enabled", False)
    )
    _write_cached_channel_enabled(guild_id, channel_id, bool(enabled))
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
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    _write_cached_channel_enabled(guild_id, channel_id, bool(enabled))


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
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    _write_cached_channel_enabled(guild_id, channel_id, bool(new_value))

    return new_value


async def get_item_suggestions_mode_enabled(guild_id: str) -> bool:
    """Return whether picture suggestion mode is enabled for this guild."""
    guild_id = str(guild_id)

    cached_enabled = _read_cached_mode_enabled(guild_id)
    if cached_enabled is not None:
        return cached_enabled

    path = get_guild_settings_path(guild_id)

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)

    enabled = bool(data.get("item_suggestions_enabled", False))
    _write_cached_mode_enabled(guild_id, enabled)
    return enabled


async def set_item_suggestions_mode_enabled(guild_id: str, enabled: bool):
    """Set whether picture suggestion mode is enabled for this guild."""
    guild_id = str(guild_id)
    path = get_guild_settings_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(int(guild_id)):
        data = await asyncio.to_thread(_read_json_file, path)
        data["item_suggestions_enabled"] = bool(enabled)
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    _write_cached_mode_enabled(guild_id, bool(enabled))


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
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    for channel_id in normalized_ids:
        _write_cached_channel_enabled(guild_id, channel_id, bool(enabled))
    if enabled:
        _write_cached_mode_enabled(guild_id, True)


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
        await asyncio.to_thread(_write_atomic_json, path, temp_path, data)

    _clear_cached_channels_for_guild(guild_id)
    _write_cached_mode_enabled(guild_id, False)

    return cleared
