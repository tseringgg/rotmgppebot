import os
import json
import asyncio

# Directory to store per-guild player data
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# Dictionary of asyncio Locks — one per guild
_locks = {}

def get_lock(guild_id: int):
    """Return or create a lock for this guild."""
    if guild_id not in _locks:
        _locks[guild_id] = asyncio.Lock()
    return _locks[guild_id]

def get_guild_data_path(guild_id: int) -> str:
    """Return the file path for this guild's data file."""
    return os.path.join(DATA_DIR, f"{guild_id}_loot_records.json")


# -------------------------------------------------------------------------
# Core read/write functions
# -------------------------------------------------------------------------

async def load_player_records(guild_id: int):
    """Load player records for a specific guild safely."""
    path = get_guild_data_path(guild_id)
    if not os.path.exists(path):
        return {}

    async with get_lock(guild_id):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

async def save_player_records(guild_id: int, records: dict):
    """Save player records for a specific guild safely."""
    path = get_guild_data_path(guild_id)
    async with get_lock(guild_id):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)


# -------------------------------------------------------------------------
# Player utilities
# -------------------------------------------------------------------------

def ensure_player_exists(records: dict, player_name: str):
    """Ensure a player entry exists with at least one PPE."""
    key = player_name.lower()
    if key not in records:
        records[key] = {"ppes": [], "active_ppe": None}
    return key

def get_active_ppe(player_data: dict):
    """Return the active PPE dict, or None."""
    active_id = player_data.get("active_ppe")
    for ppe in player_data.get("ppes", []):
        if ppe["id"] == active_id:
            return ppe
    return None

