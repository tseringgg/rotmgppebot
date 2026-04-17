"""Utilities for managing duo PPE partner linkages."""

import asyncio
import json
import os
from typing import Any, Dict

import discord

from utils.player_records import DATA_DIR, get_lock


def _group_ppes_path(guild_id: int) -> str:
    """Get the path to the group PPEs file for a guild."""
    return os.path.join(DATA_DIR, f"{guild_id}_group_ppes.json")


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
    with lock:
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
    with lock:
        loop = asyncio.get_event_loop()
        path = _group_ppes_path(guild_id)
        # Convert int keys to strings for JSON serialization
        string_mappings = {str(k): v for k, v in mappings.items()}
        await loop.run_in_executor(None, _write_json_atomic, path, string_mappings)


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
    with lock:
        loop = asyncio.get_event_loop()
        path = _group_ppes_path(guild_id)
        # Write empty dict
        await loop.run_in_executor(None, _write_json_atomic, path, {})


__all__ = [
    "set_duo_partner",
    "get_duo_partner",
    "clear_duo_partner",
    "clear_all_group_ppes",
]
