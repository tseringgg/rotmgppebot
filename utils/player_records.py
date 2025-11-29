import os
import json
import asyncio
from typing import Dict, Any, List

from dataclass import PPEData, PlayerData

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


def normalize_ppe(ppe: dict) -> PPEData:
    return PPEData(
        id=ppe.get("id", 0),
        name=ppe.get("name", "Unknown"),
        points=float(ppe.get("points", 0)),
        loot=list(ppe.get("loot", {}))
    )


def normalize_player(player: dict) -> PlayerData:
    ppes = [normalize_ppe(p) for p in player.get("ppes", [])]

    return PlayerData(
        ppes=ppes,
        active_ppe=player.get("active_ppe"),
        is_member=bool(player.get("is_member", False)),
    )

async def load_player_records(guild_id: int) -> Dict[str, PlayerData]:
    """Load player records for a specific guild safely and non-blockingly."""
    path = get_guild_data_path(guild_id)

    if not os.path.exists(path):
        return {}

    async with get_lock(guild_id):
        try:
            raw_data = await asyncio.to_thread(_read_json_file, path)
            return {name: normalize_player(v) for name, v in raw_data.items()}
        except Exception:
            return {}  # fallback


def _read_json_file(path: str) -> Dict[str, Any]:
# def _read_json_file(path: str) -> List[PlayerRecord]:
    """Blocking helper for reading JSON safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # corrupted file
    except Exception:
        return {}  # I/O error fallback


async def save_player_records(guild_id: int, records: dict):
    """Save player records safely using atomic write."""
    path = get_guild_data_path(guild_id)
    temp_path = f"{path}.tmp"

    async with get_lock(guild_id):
        await asyncio.to_thread(_write_atomic_json, path, temp_path, records)


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

def ensure_player_exists(records: Dict[str, PlayerData], player_name: str) -> str:
    """Ensure a player entry exists with at least one PPE."""
    key = player_name.lower()
    if key not in records:
        records[key] = PlayerData(ppes=[], active_ppe=None, is_member=True)
    return key


def get_active_ppe(player_data: PlayerData) -> PPEData | None:
    """Return the active PPE dict, or None."""
    active_id = player_data.active_ppe
    for ppe in player_data.ppes:
        if ppe.id == active_id:
            return ppe
    return None
