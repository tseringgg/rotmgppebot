from __future__ import annotations

import asyncio
import glob
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.player_records import DATA_DIR, get_lock


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pending_path(guild_id: int, user_id: int) -> str:
    return os.path.join(DATA_DIR, f"{guild_id}_{user_id}_realmshark_pending.json")


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_path, path)


def _as_positive_int_str(value: Any) -> str | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return str(parsed)


def _normalize_events(raw_events: Any) -> List[Dict[str, Any]]:
    events = raw_events if isinstance(raw_events, list) else []
    normalized: List[Dict[str, Any]] = []
    for event in events[-300:]:
        if not isinstance(event, dict):
            continue
        normalized.append(
            {
                "ts": str(event.get("ts", "")),
                "item_name": str(event.get("item_name", "")),
                "item_rarity": str(event.get("item_rarity", "rare")),
                "shiny": bool(event.get("shiny", False)),
                "divine": bool(event.get("divine", False)),
                "logged_mode": str(event.get("logged_mode", "addseasonloot")),
            }
        )
    return normalized


def _normalize_pending(raw: Dict[str, Any]) -> Dict[str, Any]:
    raw_characters = raw.get("characters", {}) if isinstance(raw.get("characters", {}), dict) else {}
    characters: Dict[str, Dict[str, Any]] = {}
    for raw_character_id, raw_entry in raw_characters.items():
        character_id = _as_positive_int_str(raw_character_id)
        if character_id is None or not isinstance(raw_entry, dict):
            continue

        entry = {
            "first_seen_at": str(raw_entry.get("first_seen_at", "")),
            "last_seen_at": str(raw_entry.get("last_seen_at", "")),
            "prompted": bool(raw_entry.get("prompted", False)),
            "character_name": str(raw_entry.get("character_name", "")),
            "character_class": str(raw_entry.get("character_class", "")),
            "events": _normalize_events(raw_entry.get("events", [])),
        }
        characters[character_id] = entry

    return {
        "schema": 1,
        "updated_at": str(raw.get("updated_at", "")),
        "characters": characters,
    }


async def load_pending(guild_id: int, user_id: int) -> Dict[str, Any]:
    path = _pending_path(guild_id, user_id)

    if not os.path.exists(path):
        return {"schema": 1, "updated_at": "", "characters": {}}

    async with get_lock(guild_id):
        raw = await asyncio.to_thread(_read_json, path)
        normalized = _normalize_pending(raw if isinstance(raw, dict) else {})
        if normalized != raw:
            normalized["updated_at"] = _utc_iso_now()
            await asyncio.to_thread(_write_json_atomic, path, normalized)
        return normalized


async def save_pending(guild_id: int, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _pending_path(guild_id, user_id)
    normalized = _normalize_pending(payload if isinstance(payload, dict) else {})
    normalized["updated_at"] = _utc_iso_now()

    async with get_lock(guild_id):
        await asyncio.to_thread(_write_json_atomic, path, normalized)

    return normalized


async def append_pending_event(
    guild_id: int,
    user_id: int,
    *,
    character_id: int,
    item_name: str,
    item_rarity: str,
    shiny: bool,
    divine: bool,
    character_name: str = "",
    character_class: str = "",
) -> bool:
    data = await load_pending(guild_id, user_id)
    key = _as_positive_int_str(character_id)
    if key is None:
        return False

    characters = data.get("characters", {})
    if not isinstance(characters, dict):
        characters = {}

    now = _utc_iso_now()
    created = key not in characters
    entry = characters.get(key, {}) if isinstance(characters.get(key, {}), dict) else {}

    if "first_seen_at" not in entry or not str(entry.get("first_seen_at", "")):
        entry["first_seen_at"] = now
    entry["last_seen_at"] = now
    entry["prompted"] = bool(entry.get("prompted", False))
    if character_name:
        entry["character_name"] = str(character_name)
    if character_class:
        entry["character_class"] = str(character_class)

    events = _normalize_events(entry.get("events", []))
    events.append(
        {
            "ts": now,
            "item_name": str(item_name),
            "item_rarity": str(item_rarity),
            "shiny": bool(shiny),
            "divine": bool(divine),
            "logged_mode": "addseasonloot",
        }
    )
    entry["events"] = events[-300:]

    characters[key] = entry
    data["characters"] = characters
    await save_pending(guild_id, user_id, data)
    return created


async def get_pending_character_entry(guild_id: int, user_id: int, character_id: int) -> Dict[str, Any] | None:
    key = _as_positive_int_str(character_id)
    if key is None:
        return None

    data = await load_pending(guild_id, user_id)
    characters = data.get("characters", {}) if isinstance(data.get("characters", {}), dict) else {}
    entry = characters.get(key)
    if not isinstance(entry, dict):
        return None
    return entry


async def clear_pending_character(guild_id: int, user_id: int, character_id: int) -> bool:
    key = _as_positive_int_str(character_id)
    if key is None:
        return False

    data = await load_pending(guild_id, user_id)
    characters = data.get("characters", {}) if isinstance(data.get("characters", {}), dict) else {}
    if key not in characters:
        return False

    del characters[key]
    data["characters"] = characters
    await save_pending(guild_id, user_id, data)
    return True


async def pop_pending_events_for_character(guild_id: int, user_id: int, character_id: int) -> List[Dict[str, Any]]:
    key = _as_positive_int_str(character_id)
    if key is None:
        return []

    data = await load_pending(guild_id, user_id)
    characters = data.get("characters", {}) if isinstance(data.get("characters", {}), dict) else {}
    entry = characters.get(key)
    if not isinstance(entry, dict):
        return []

    events = _normalize_events(entry.get("events", []))
    del characters[key]
    data["characters"] = characters
    await save_pending(guild_id, user_id, data)
    return events


async def migrate_legacy_pending_map(guild_id: int, user_id: int, pending_map: Dict[str, Any]) -> None:
    if not isinstance(pending_map, dict) or not pending_map:
        return

    data = await load_pending(guild_id, user_id)
    characters = data.get("characters", {}) if isinstance(data.get("characters", {}), dict) else {}

    for raw_character_id, raw_entry in pending_map.items():
        key = _as_positive_int_str(raw_character_id)
        if key is None or not isinstance(raw_entry, dict):
            continue

        existing = characters.get(key, {}) if isinstance(characters.get(key, {}), dict) else {}
        merged_events = _normalize_events(existing.get("events", [])) + _normalize_events(raw_entry.get("events", []))
        merged_events = merged_events[-300:]

        first_seen = str(existing.get("first_seen_at", "")) or str(raw_entry.get("first_seen_at", ""))
        last_seen = str(raw_entry.get("last_seen_at", "")) or str(existing.get("last_seen_at", ""))

        characters[key] = {
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "prompted": bool(existing.get("prompted", False) or raw_entry.get("prompted", False)),
            "character_name": str(existing.get("character_name", "")) or str(raw_entry.get("character_name", "")),
            "character_class": str(existing.get("character_class", "")) or str(raw_entry.get("character_class", "")),
            "events": merged_events,
        }

    data["characters"] = characters
    await save_pending(guild_id, user_id, data)


async def clear_pending_for_user(guild_id: int, user_id: int) -> bool:
    path = _pending_path(guild_id, user_id)
    deleted = False

    async with get_lock(guild_id):
        if os.path.exists(path):
            await asyncio.to_thread(os.remove, path)
            deleted = True

        temp_path = f"{path}.tmp"
        if os.path.exists(temp_path):
            await asyncio.to_thread(os.remove, temp_path)

    return deleted


async def clear_all_pending_for_guild(guild_id: int) -> int:
    pattern = os.path.join(DATA_DIR, f"{guild_id}_*_realmshark_pending.json")
    temp_pattern = os.path.join(DATA_DIR, f"{guild_id}_*_realmshark_pending.json.tmp")
    deleted = 0

    async with get_lock(guild_id):
        paths = await asyncio.to_thread(glob.glob, pattern)
        temp_paths = await asyncio.to_thread(glob.glob, temp_pattern)

        for path in paths:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
                deleted += 1

        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                await asyncio.to_thread(os.remove, temp_path)

    return deleted
