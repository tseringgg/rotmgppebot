"""Utilities for managing duo PPE partner linkages."""

import asyncio
import json
import os
from typing import Any, Dict
from uuid import uuid4

import discord

from utils.player_records import DATA_DIR, get_lock, load_player_records


def _group_ppes_path(guild_id: int) -> str:
    """Get the path to the group PPEs file for a guild."""
    return os.path.join(DATA_DIR, f"{guild_id}_group_ppes.json")


def _duo_requests_path(guild_id: int) -> str:
    """Get the path to the pending duo request file for a guild."""
    return os.path.join(DATA_DIR, f"{guild_id}_duo_requests.json")


def _read_json(path: str) -> Dict[str, Any]:
    """Read JSON from file, returning empty dict if file doesn't exist."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Write JSON to file atomically using a temporary file."""
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_path, path)


async def _load_group_ppes(guild_id: int) -> Dict[int, int]:
    """Load duo partner mappings from disk.
    
    Returns a dict mapping user_id -> partner_user_id for all active duo partnerships.
    """
    lock = get_lock(guild_id)
    async with lock:
        loop = asyncio.get_event_loop()
        path = _group_ppes_path(guild_id)
        data = await loop.run_in_executor(None, _read_json, path)
        
        # Convert string keys back to ints
        result: Dict[int, int] = {}
        for key_str, value in data.items():
            try:
                key = int(key_str)
                val = int(value)
                if key > 0 and val > 0:
                    result[key] = val
            except (ValueError, TypeError):
                pass
        return result


async def _save_group_ppes(guild_id: int, mappings: Dict[int, int]) -> None:
    """Save duo partner mappings to disk.
    
    Args:
        guild_id: The guild to save for
        mappings: Dict mapping user_id -> partner_user_id
    """
    lock = get_lock(guild_id)
    async with lock:
        loop = asyncio.get_event_loop()
        path = _group_ppes_path(guild_id)
        # Convert int keys to strings for JSON serialization
        string_mappings = {str(k): v for k, v in mappings.items()}
        await loop.run_in_executor(None, _write_json_atomic, path, string_mappings)


async def _load_duo_requests(guild_id: int) -> Dict[int, Dict[str, Any]]:
    """Load pending duo request metadata for a guild."""
    lock = get_lock(guild_id)
    async with lock:
        loop = asyncio.get_event_loop()
        path = _duo_requests_path(guild_id)
        data = await loop.run_in_executor(None, _read_json, path)

        result: Dict[int, Dict[str, Any]] = {}
        for key_str, value in data.items():
            try:
                requester_id = int(key_str)
            except (TypeError, ValueError):
                continue
            if requester_id <= 0 or not isinstance(value, dict):
                continue

            partner_id = value.get("partner_id")
            token = str(value.get("token", "")).strip()
            channel_id = value.get("channel_id")
            try:
                partner_id_int = int(partner_id)
            except (TypeError, ValueError):
                continue
            if partner_id_int <= 0 or not token:
                continue

            normalized_request: Dict[str, Any] = {
                "partner_id": partner_id_int,
                "token": token,
            }
            try:
                channel_id_int = int(channel_id)
            except (TypeError, ValueError):
                channel_id_int = None
            if channel_id_int is not None and channel_id_int > 0:
                normalized_request["channel_id"] = channel_id_int
            context = value.get("context")
            if isinstance(context, dict):
                normalized_request["context"] = dict(context)
            result[requester_id] = normalized_request
        return result


async def _save_duo_requests(guild_id: int, requests: Dict[int, Dict[str, Any]]) -> None:
    """Save pending duo request metadata for a guild."""
    lock = get_lock(guild_id)
    async with lock:
        loop = asyncio.get_event_loop()
        path = _duo_requests_path(guild_id)
        payload: Dict[str, Any] = {}
        for requester_id, data in requests.items():
            if requester_id <= 0 or not isinstance(data, dict):
                continue
            partner_id = data.get("partner_id")
            token = str(data.get("token", "")).strip()
            if not token:
                continue
            try:
                partner_id_int = int(partner_id)
            except (TypeError, ValueError):
                continue
            if partner_id_int <= 0:
                continue

            normalized_request: Dict[str, Any] = {
                "partner_id": partner_id_int,
                "token": token,
            }
            channel_id = data.get("channel_id")
            try:
                channel_id_int = int(channel_id)
            except (TypeError, ValueError):
                channel_id_int = None
            if channel_id_int is not None and channel_id_int > 0:
                normalized_request["channel_id"] = channel_id_int
            context = data.get("context")
            if isinstance(context, dict):
                normalized_request["context"] = dict(context)
            payload[str(requester_id)] = normalized_request

        await loop.run_in_executor(None, _write_json_atomic, path, payload)


async def set_duo_partner(interaction: discord.Interaction, user_id: int, partner_id: int) -> None:
    """Set a duo partnership between two users.
    
    Creates bidirectional mapping: user_id <-> partner_id
    
    Args:
        interaction: Discord interaction (used to get guild_id)
        user_id: First user ID
        partner_id: Second user ID (the partner)
    """
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")
    
    if user_id <= 0 or partner_id <= 0:
        raise ValueError("User IDs must be positive integers.")
    
    guild_id = interaction.guild.id
    mappings = await _load_group_ppes(guild_id)
    
    # Create bidirectional mapping
    mappings[user_id] = partner_id
    mappings[partner_id] = user_id
    
    await _save_group_ppes(guild_id, mappings)


async def set_duo_request(
    interaction: discord.Interaction,
    requester_id: int,
    partner_id: int,
    *,
    channel_id: int | None = None,
    context: Dict[str, Any] | None = None,
) -> str:
    """Record the current pending duo request for a requester.

    Returns a new request token that must match when the invite is accepted.
    """
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    if requester_id <= 0 or partner_id <= 0:
        raise ValueError("User IDs must be positive integers.")

    guild_id = interaction.guild.id
    requests = await _load_duo_requests(guild_id)
    token = uuid4().hex
    request_payload: Dict[str, Any] = {
        "partner_id": int(partner_id),
        "token": token,
    }
    if isinstance(channel_id, int) and channel_id > 0:
        request_payload["channel_id"] = int(channel_id)
    if isinstance(context, dict):
        request_payload["context"] = dict(context)
    requests[int(requester_id)] = request_payload
    await _save_duo_requests(guild_id, requests)
    return token


async def get_duo_request(interaction: discord.Interaction, requester_id: int) -> Dict[str, Any] | None:
    """Return the active pending duo request for a requester, if any."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    guild_id = interaction.guild.id
    requests = await _load_duo_requests(guild_id)
    request = requests.get(int(requester_id))
    return dict(request) if isinstance(request, dict) else None


async def clear_duo_request(interaction: discord.Interaction, requester_id: int) -> None:
    """Clear the active pending duo request for a requester, if any."""
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")

    guild_id = interaction.guild.id
    requests = await _load_duo_requests(guild_id)
    if int(requester_id) in requests:
        requests.pop(int(requester_id), None)
        await _save_duo_requests(guild_id, requests)


async def duo_request_is_current(
    interaction: discord.Interaction,
    requester_id: int,
    partner_id: int,
    token: str,
) -> bool:
    """Check whether a DM invite still matches the latest pending duo request."""
    request = await get_duo_request(interaction, requester_id)
    if request is None:
        return False
    return int(request.get("partner_id", 0) or 0) == int(partner_id) and str(request.get("token", "")).strip() == str(token).strip()


async def get_duo_partner(interaction: discord.Interaction, user_id: int) -> int | None:
    """Get the duo partner ID for a user, if set.
    
    Args:
        interaction: Discord interaction (used to get guild_id)
        user_id: The user ID to look up
        
    Returns:
        The partner user ID, or None if not set
    """
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")
    
    guild_id = interaction.guild.id
    mappings = await _load_group_ppes(guild_id)
    
    return mappings.get(user_id)


async def clear_duo_partner(interaction: discord.Interaction, user_id: int) -> None:
    """Clear the duo partnership for a user.
    
    Removes the bidirectional mapping for the user.
    
    Args:
        interaction: Discord interaction (used to get guild_id)
        user_id: The user ID to clear
    """
    if interaction.guild is None:
        raise ValueError("This action can only be used in a server.")
    
    guild_id = interaction.guild.id
    mappings = await _load_group_ppes(guild_id)
    
    # Remove both directions of the mapping
    if user_id in mappings:
        partner_id = mappings.pop(user_id)
        mappings.pop(partner_id, None)
    
    await _save_group_ppes(guild_id, mappings)


async def clear_all_group_ppes(guild_id: int) -> None:
    """Clear all duo partnerships for a guild.
    
    This is called during season reset to clear PPE characters.
    
    Args:
        guild_id: The guild to clear partnerships for
    """
    lock = get_lock(guild_id)
    async with lock:
        loop = asyncio.get_event_loop()
        path = _group_ppes_path(guild_id)
        # Write empty dict
        await loop.run_in_executor(None, _write_json_atomic, path, {})


def duo_partner_id_from_options(options: Any) -> int | None:
    if not isinstance(options, dict) or not bool(options.get("duo_enabled", False)):
        return None

    raw_partner = options.get("duo_partner_id")
    try:
        partner_id = int(raw_partner)
    except (TypeError, ValueError):
        return None
    return partner_id if partner_id > 0 else None


def duo_link_id_from_options(options: Any) -> str | None:
    if not isinstance(options, dict):
        return None

    raw = str(options.get("duo_link_id", "")).strip()
    if not raw or raw.lower() == "none":
        return None
    return raw


async def get_duo_link_id_for_user(interaction: discord.Interaction, user_id: int) -> str | None:
    partner_id = await get_duo_partner(interaction, user_id)
    if partner_id is None:
        return None

    records = await load_player_records(interaction)
    partner_data = records.get(int(partner_id))
    if partner_data is None:
        return None

    partner_ppes = getattr(partner_data, "ppes", None)
    if not isinstance(partner_ppes, list):
        return None

    for ppe in partner_ppes:
        options = getattr(ppe, "ppe_type_options", None)
        if duo_partner_id_from_options(options) != int(user_id):
            continue

        link_id = duo_link_id_from_options(options)
        if link_id is not None:
            return link_id

    return None


__all__ = [
    "set_duo_partner",
    "get_duo_partner",
    "clear_duo_partner",
    "clear_all_group_ppes",
    "set_duo_request",
    "get_duo_request",
    "clear_duo_request",
    "duo_request_is_current",
    "duo_partner_id_from_options",
    "duo_link_id_from_options",
    "get_duo_link_id_for_user",
]
