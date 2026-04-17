"""Utilities for player records."""

import os
import json
import asyncio
import re
import glob
from typing import Dict, Any, List

from dataclasses import asdict

import discord
from dataclass import Loot, PPEData, PlayerData, Bonus, TeamData, QuestData
from utils.loot_constants import normalize_rarity, rarity_rank
from utils.ppe_types import normalize_ppe_type

_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def _normalize_item_name(name: str) -> str:
    if not name:
        return ""
    normalized = name
    normalized = normalized.replace("\u2018", "'").replace("\u2019", "'").replace("\u02bc", "'").replace("\u2032", "'").replace("\u00b4", "'").replace("`", "'")
    for dash in _DASH_VARIANTS:
        normalized = normalized.replace(dash, "-")
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return " ".join(normalized.split()).strip()


def _normalize_rarity(value: Any, fallback: str = "common") -> str:
    return normalize_rarity(value, fallback)


def _rarity_rank(value: str) -> int:
    return rarity_rank(value)


def highest_rarity(first: str, second: str) -> str:
    return first if _rarity_rank(first) >= _rarity_rank(second) else second

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


def clear_guild_lock(guild_id: int) -> None:
    """Drop the per-guild lock when guild-scoped state can be released."""
    _locks.pop(int(guild_id), None)


def get_lock_count() -> int:
    return len(_locks)


def get_player_data_path(guild_id: int, user_id: int) -> str:
    """Return the file path for one player's data file."""
    return os.path.join(DATA_DIR, f"{guild_id}_{user_id}_loot_records.json")


def get_guild_player_data_pattern(guild_id: int) -> str:
    """Return glob pattern for all player record files in a guild."""
    return os.path.join(DATA_DIR, f"{guild_id}_*_loot_records.json")


def _parse_user_id_from_player_data_path(guild_id: int, path: str) -> int | None:
    """Extract the user_id from a per-user player-record path."""
    filename = os.path.basename(path)
    match = re.match(r"^(\d+)_(\d+)_loot_records\.json$", filename)
    if not match:
        return None

    parsed_guild_id = int(match.group(1))
    parsed_user_id = int(match.group(2))
    if parsed_guild_id != guild_id:
        return None
    return parsed_user_id


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
        legacy_divine = bool(loot_dict.get("divine", False))
        rarity = _normalize_rarity(loot_dict.get("rarity"), "divine" if legacy_divine else "common")
        raw_logged_times = loot_dict.get("logged_times", [])
        logged_times: list[int] = []
        if isinstance(raw_logged_times, list):
            for raw_ts in raw_logged_times:
                try:
                    parsed_ts = int(raw_ts)
                except (TypeError, ValueError):
                    continue
                if parsed_ts > 0:
                    logged_times.append(parsed_ts)
        logged_times.sort()

        if not logged_times:
            logged_times = []

        normalized_loot = {
            "item_name": loot_dict.get("item_name", "Unknown Item"),
            "quantity": loot_dict.get("quantity", 0),
            "shiny": loot_dict.get("shiny", False),
            "rarity": rarity,
            "logged_times": logged_times,
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
    
    # Load completed_sets (defaults to empty list if not present)
    completed_sets_raw = ppe.get("completed_sets", [])
    completed_sets = []
    if isinstance(completed_sets_raw, list):
        completed_sets = [str(s) for s in completed_sets_raw if s]
    
    return PPEData(
        id=ppe.get("id", 0),
        name=ppe.get("name", "Unknown"),
        points=float(ppe.get("points", 0)),
        loot=loot_objects,
        bonuses=bonus_objects,
        ppe_type=normalize_ppe_type(ppe.get("ppe_type")),
        completed_sets=completed_sets,
    )


def normalize_player(player: dict) -> PlayerData:
    ppes = [normalize_ppe(p) for p in player.get("ppes", [])]

    def safe_optional_non_negative_int(value) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return max(0, parsed)

    def safe_str_list(value) -> List[str]:
        """Coerce unknown/legacy values into a clean list of strings."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return []

    quests_raw = player.get("quests", {}) if isinstance(player.get("quests", {}), dict) else {}
    normalized_quests = QuestData(
        # Prefer unified quests field, but gracefully fall back to legacy keys.
        current_items=safe_str_list(quests_raw.get("current_items", player.get("current_item_quests", []))),
        current_shinies=safe_str_list(quests_raw.get("current_shinies", player.get("current_shiny_quests", []))),
        current_skins=safe_str_list(quests_raw.get("current_skins", player.get("current_skin_quests", []))),
        completed_items=safe_str_list(quests_raw.get("completed_items", player.get("completed_item_quests", []))),
        completed_shinies=safe_str_list(quests_raw.get("completed_shinies", player.get("completed_shiny_quests", []))),
        completed_skins=safe_str_list(quests_raw.get("completed_skins", player.get("completed_skin_quests", []))),
    )
    
    season_item_history = player.get("season_item_history", {})
    if not isinstance(season_item_history, dict):
        season_item_history = {}

    normalized_player = PlayerData(
        ppes=ppes,
        active_ppe=player.get("active_ppe"),
        is_member=bool(player.get("is_member", False)),
        season_item_history=season_item_history,
        team_name=player.get("team_name", None),
        quests=normalized_quests,
        quest_resets_remaining=safe_optional_non_negative_int(player.get("quest_resets_remaining")),
    )
    return normalized_player

async def load_player_records(interaction: discord.Interaction) -> Dict[int, PlayerData]:
    """Load player records for a specific guild safely and non-blockingly."""
    if interaction.guild is None:
            raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    pattern = get_guild_player_data_pattern(guild_id)

    async with get_lock(guild_id):
        try:
            paths = await asyncio.to_thread(glob.glob, pattern)
            loaded_records: Dict[int, PlayerData] = {}

            for path in paths:
                user_id = _parse_user_id_from_player_data_path(guild_id, path)
                if user_id is None:
                    continue

                raw_data = await asyncio.to_thread(_read_json_file, path)
                if not isinstance(raw_data, dict):
                    continue

                # Current format stores exactly one player's payload in each file.
                if "ppes" in raw_data:
                    loaded_records[user_id] = normalize_player(raw_data)
                    continue

                # Allow accidental nested format and read the matching user entry if present.
                nested = raw_data.get(str(user_id))
                if isinstance(nested, dict):
                    loaded_records[user_id] = normalize_player(nested)

            return loaded_records
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
    pattern = get_guild_player_data_pattern(guild_id)

    normalized_records: Dict[int, PlayerData] = {}
    for user_id, data in records.items():
        normalized_records[int(user_id)] = data

    async with get_lock(guild_id):
        existing_paths = await asyncio.to_thread(glob.glob, pattern)
        existing_ids: set[int] = set()
        for existing_path in existing_paths:
            parsed_user_id = _parse_user_id_from_player_data_path(guild_id, existing_path)
            if parsed_user_id is not None:
                existing_ids.add(parsed_user_id)

        desired_ids = set(normalized_records.keys())

        for user_id, data in normalized_records.items():
            path = get_player_data_path(guild_id, user_id)
            temp_path = f"{path}.tmp"
            await asyncio.to_thread(_write_atomic_json, path, temp_path, _serialize_player_data(data))

        stale_ids = existing_ids - desired_ids
        for stale_user_id in stale_ids:
            stale_path = get_player_data_path(guild_id, stale_user_id)
            await asyncio.to_thread(_delete_file_if_exists, stale_path)


def _serialize_player_data(data: PlayerData) -> Dict[str, Any]:
    """Convert PlayerData into JSON-ready dict for one per-user file."""
    return {
        "is_member": data.is_member,
        "ppes": [
            {
                "id": p.id,
                "name": p.name,
                "points": p.points,
                "loot": [
                    {
                        "item_name": l.item_name,
                        "quantity": l.quantity,
                        "shiny": l.shiny,
                        "rarity": l.rarity,
                        "logged_times": list(getattr(l, "logged_times", [])),
                    }
                    for l in p.loot
                ],
                "bonuses": [asdict(b) for b in p.bonuses],
                "ppe_type": normalize_ppe_type(getattr(p, "ppe_type", None)),
                "completed_sets": list(getattr(p, "completed_sets", [])),
            }
            for p in data.ppes
        ],
        "active_ppe": data.active_ppe,
        "season_item_history": dict(getattr(data, "season_item_history", {})),
        "team_name": data.team_name,
        "quest_resets_remaining": data.quest_resets_remaining,
        "quests": {
            "current_items": data.quests.current_items,
            "current_shinies": data.quests.current_shinies,
            "current_skins": data.quests.current_skins,
            "completed_items": data.quests.completed_items,
            "completed_shinies": data.quests.completed_shinies,
            "completed_skins": data.quests.completed_skins,
        },
    }


def _write_atomic_json(path: str, temp_path: str, data: dict):
    """Write JSON atomically to avoid corruption."""
    # Write to temp file first
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

    # Optional: backup old file
    # if os.path.exists(path):
    #     os.replace(path, f"{path}.bak")

    # Atomically replace the real file
    os.replace(temp_path, path)


def _delete_file_if_exists(path: str):
    """Delete a file if present; ignore races/missing files."""
    try:
        os.remove(path)
    except FileNotFoundError:
        return


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

def get_item_from_ppe(active_ppe: PPEData, item_name: str, shiny: bool, rarity: str | None = None) -> Loot | None:
    """Return the Loot object from active PPE by item name, or None."""
    requested_rarity = _normalize_rarity(rarity, "common")
    for item in active_ppe.loot:
        if (
            item.item_name.lower() == _normalize_item_name(item_name).lower()
            and item.shiny == shiny
            and _normalize_rarity(getattr(item, "rarity", None), "common") == requested_rarity
            and item.quantity > 0
        ):
            return item
    return None


async def is_team_leader(interaction: discord.Interaction, member_id: int, team_name: str) -> bool:
    """Check if a member is the leader of a specific team."""
    try:
        teams = await load_teams(interaction)
        # Find team (case-insensitive)
        actual_team_name = None
        for team_key in teams:
            if team_key.lower() == team_name.lower():
                actual_team_name = team_key
                break
        
        if not actual_team_name:
            return False
        
        team = teams[actual_team_name]
        return team.leader_id == member_id
    except Exception:
        return False


# -------------------------------------------------------------------------
# Team management functions
# -------------------------------------------------------------------------

def get_guild_teams_path(guild_id: int) -> str:
    """Return the file path for this guild's teams data file."""
    return os.path.join(DATA_DIR, f"{guild_id}_teams.json")


def normalize_team(team: dict) -> TeamData:
    """Convert a dict representation of a team to TeamData."""
    return TeamData(
        name=team.get("name", "Unknown Team"),
        leader_id=int(team.get("leader_id", 0)),
        members=[int(m) for m in team.get("members", [])]
    )


async def load_teams(interaction: discord.Interaction) -> Dict[str, TeamData]:
    """Load all teams for a guild. Key is team name (case-insensitive, stored as-is)."""
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    path = get_guild_teams_path(guild_id)

    if not os.path.exists(path):
        return {}

    async with get_lock(guild_id):
        try:
            raw_data = await asyncio.to_thread(_read_json_file, path)
            teams = {}
            for team_name, team_data in raw_data.items():
                teams[team_name] = normalize_team(team_data)
            return teams
        except Exception as e:
            print(f"Error loading teams for guild {guild_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {}


async def save_teams(interaction: discord.Interaction, teams: Dict[str, TeamData]):
    """Save all teams for a guild safely using atomic write."""
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    path = get_guild_teams_path(guild_id)
    temp_path = f"{path}.tmp"

    # Convert TeamData objects into plain dicts
    json_ready = {
        team_name: {
            "name": team.name,
            "leader_id": team.leader_id,
            "members": team.members
        }
        for team_name, team in teams.items()
    }
    async with get_lock(guild_id):
        await asyncio.to_thread(_write_atomic_json, path, temp_path, json_ready)


# Channel-level settings helpers were moved to utils.settings.channel_settings.