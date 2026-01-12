from csv import Error
import os
import json
import asyncio
import re
from typing import Dict, Any, List

from dataclasses import asdict

import discord
from dataclass import Loot, PPEData, PlayerData, Bonus

# Persistent data directory (Railway Volume)
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

# Per-guild asyncio locks
_locks: Dict[int, asyncio.Lock] = {}


def get_lock(guild_id: int) -> asyncio.Lock:
    """Return or create a lock for this guild."""
    if guild_id not in _locks:
        _locks[guild_id] = asyncio.Lock()
    return _locks[guild_id]


def get_guild_data_path(guild_id: int) -> str:
    """Return the file path for this guild's data file."""
    return os.path.join(DATA_DIR, f"{guild_id}_loot_records.json")


# -------------------------------------------------------------------------
# Core read/write functions (safe + async-friendly)
# -------------------------------------------------------------------------


# def normalize_ppe(ppe: dict) -> PPEData:
#     return PPEData(
#         id=ppe.get("id", 0),
#         name=ppe.get("name", "Unknown"),
#         points=float(ppe.get("points", 0)),
#         loot=list(ppe.get("loot", {}))
#     )

def normalize_ppe(ppe: dict) -> PPEData:
    
    loot_dicts = ppe.get("loot", [])
    loot_objects = []
    
    for loot_dict in loot_dicts:
        # Ensure all required fields exist with defaults
        normalized_loot = {
            "item_name": loot_dict.get("item_name", "Unknown Item"),
            "quantity": loot_dict.get("quantity", 0),
            "divine": loot_dict.get("divine", False),
            "shiny": loot_dict.get("shiny", False)
        }
        loot_objects.append(Loot(**normalized_loot))
    
    # Handle bonuses migration - if bonuses field doesn't exist, create empty list
    bonus_dicts = ppe.get("bonuses", [])
    bonus_objects = []
    
    for bonus_dict in bonus_dicts:
        # Ensure all required fields exist with defaults
        normalized_bonus = {
            "name": bonus_dict.get("name", "Unknown Bonus"),
            "points": float(bonus_dict.get("points", 0)),
            "repeatable": bool(bonus_dict.get("repeatable", False)),
            "quantity": int(bonus_dict.get("quantity", 1))  # Default quantity to 1 for old bonuses
        }
        bonus_objects.append(Bonus(**normalized_bonus))
    
    return PPEData(
        id=ppe.get("id", 0),
        name=ppe.get("name", "Unknown"),
        points=float(ppe.get("points", 0)),
        loot=loot_objects,
        bonuses=bonus_objects
    )


def normalize_player(player: dict) -> PlayerData:
    ppes = [normalize_ppe(p) for p in player.get("ppes", [])]
    
    # Handle unique_items migration - rebuild from PPEs if missing
    unique_items_list = player.get("unique_items", None)
    if unique_items_list is not None:
        # Load from saved data (list of tuples)
        unique_items = set(tuple(item) for item in unique_items_list)
    else:
        # Rebuild from all PPEs for migration
        print("Migrating unique_items from PPE loot data...")
        unique_items = set()
        for ppe in ppes:
            for loot in ppe.loot:
                unique_items.add((loot.item_name, loot.shiny))

    return PlayerData(
        ppes=ppes,
        active_ppe=player.get("active_ppe"),
        is_member=bool(player.get("is_member", False)),
        unique_items=unique_items
    )

async def load_player_records(interaction: discord.Interaction) -> Dict[int, PlayerData]:
    """Load player records for a specific guild safely and non-blockingly."""
    if interaction.guild is None:
            raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    path = get_guild_data_path(guild_id)

    if not os.path.exists(path):
        return {}

    async with get_lock(guild_id):
        try:
            raw_data = await asyncio.to_thread(_read_json_file, path)
            # Handle migration from string keys to int keys
            migrated_data = {}
            for key, value in raw_data.items():
                try:
                    # Try to convert key to int (new format)
                    int_key = int(key)
                    migrated_data[int_key] = normalize_player(value)
                except ValueError:
                    # Skip string keys (old format) for now
                    # You could add logic here to migrate based on username lookup if needed
                    print(f"Skipping old string key: {key}")
                    continue
            return migrated_data
        except Exception as e:
            print(f"Error loading player records for guild {guild_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {}  # fallback


def _read_json_file(path: str) -> Dict[str, Any]:
    """Blocking helper for reading JSON safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # corrupted file
    except Exception:
        return {}  # I/O error fallback


async def save_player_records(interaction: discord.Interaction, records: Dict[int, PlayerData]):
    """Save player records safely using atomic write."""
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    path = get_guild_data_path(guild_id)
    temp_path = f"{path}.tmp"

    # Convert typed PlayerData objects into plain dicts
    json_ready = {
        str(user_id): {  # Convert int key to string for JSON
            "is_member": data.is_member,
            "ppes": [
                {
                    "id": p.id,
                    "name": p.name,
                    "points": p.points,
                    "loot": [asdict(l) for l in p.loot],
                    "bonuses": [asdict(b) for b in p.bonuses]
                }
                for p in data.ppes
            ],
            "active_ppe": data.active_ppe,
            "unique_items": list(data.unique_items)  # Convert set to list for JSON
        }
        for user_id, data in records.items()
    }
    async with get_lock(guild_id):
        await asyncio.to_thread(_write_atomic_json, path, temp_path, json_ready)


def _write_atomic_json(path: str, temp_path: str, data: dict):
    """Write JSON atomically to avoid corruption."""
    # Write to temp file first
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Optional: backup old file
    # if os.path.exists(path):
    #     os.replace(path, f"{path}.bak")

    # Atomically replace the real file
    os.replace(temp_path, path)


# -------------------------------------------------------------------------
# Player utilities
# -------------------------------------------------------------------------

def ensure_player_exists(records: Dict[int, PlayerData], player_id: int) -> int:
    """Ensure a player entry exists with at least one PPE."""
    key = player_id
    if key not in records:
        records[key] = PlayerData(ppes=[], active_ppe=None, is_member=True)
    return key


def get_active_ppe(player_data: PlayerData) -> PPEData:
    """Return the active PPE dict, or None."""
    active_id = player_data.active_ppe
    for ppe in player_data.ppes:
        if ppe.id == active_id:
            return ppe
    raise ValueError("Active PPE ID not found in player's PPE records.")

async def get_active_ppe_of_user(interaction: discord.Interaction) -> PPEData:
    """Return the active PPE dict of the user, or None."""
    if interaction.guild is None:
            raise ValueError("Interaction guild is None.")
    member = interaction.user
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, member.id)
    if key not in records:
        raise ValueError("Player record not found after ensuring existence.")
    player_data = records[key]
    if not player_data.ppes:
        raise ValueError("Player has no PPE records.")
    await save_player_records(interaction, records)
    return get_active_ppe(player_data)

def get_item_from_ppe(active_ppe: PPEData, item_name: str, divine: bool, shiny: bool) -> Loot | None:
    """Return the Loot object from active PPE by item name, or None."""
    for item in active_ppe.loot:
        if item.item_name.lower() == item_name.lower() and item.divine == divine and item.shiny == shiny and item.quantity > 0:
            return item
    return None