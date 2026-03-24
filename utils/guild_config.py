import asyncio
import json
import os
from typing import Any, Dict

import discord

from utils.player_records import DATA_DIR, get_lock

_DEFAULT_CONFIG: Dict[str, Any] = {
    "quest_settings": {
        "regular_target": 8,
        "shiny_target": 3,
        "skin_target": 1,
        "regular_points": 5,
        "shiny_points": 10,
        "skin_points": 15,
        "num_resets": 3,
    },
    "realmshark_settings": {
        "enabled": False,
        "mode": "addloot",
        "links": {},
        "announce_channel_id": 0,
    },
}


def _config_path(guild_id: int) -> str:
    return os.path.join(DATA_DIR, f"{guild_id}_config.json")


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


def _normalized_targets(config: Dict[str, Any]) -> Dict[str, int]:
    settings = config.get("quest_settings", {}) if isinstance(config.get("quest_settings", {}), dict) else {}

    def _as_non_negative_int(value: Any, fallback: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(0, parsed)

    return {
        "regular_target": _as_non_negative_int(settings.get("regular_target"), _DEFAULT_CONFIG["quest_settings"]["regular_target"]),
        "shiny_target": _as_non_negative_int(settings.get("shiny_target"), _DEFAULT_CONFIG["quest_settings"]["shiny_target"]),
        "skin_target": _as_non_negative_int(settings.get("skin_target"), _DEFAULT_CONFIG["quest_settings"]["skin_target"]),
        "regular_points": _as_non_negative_int(settings.get("regular_points"), _DEFAULT_CONFIG["quest_settings"]["regular_points"]),
        "shiny_points": _as_non_negative_int(settings.get("shiny_points"), _DEFAULT_CONFIG["quest_settings"]["shiny_points"]),
        "skin_points": _as_non_negative_int(settings.get("skin_points"), _DEFAULT_CONFIG["quest_settings"]["skin_points"]),
        "num_resets": _as_non_negative_int(settings.get("num_resets"), _DEFAULT_CONFIG["quest_settings"]["num_resets"]),
    }


def _normalized_realmshark_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    settings = config.get("realmshark_settings", {}) if isinstance(config.get("realmshark_settings", {}), dict) else {}

    mode = str(settings.get("mode", _DEFAULT_CONFIG["realmshark_settings"]["mode"]))
    if mode not in {"addloot", "addseasonloot"}:
        mode = _DEFAULT_CONFIG["realmshark_settings"]["mode"]

    raw_links = settings.get("links", {})
    links: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw_links, dict):
        for token, link_data in raw_links.items():
            if not isinstance(token, str) or not token.strip():
                continue
            if not isinstance(link_data, dict):
                continue

            user_id = link_data.get("user_id")
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                continue

            raw_last_seen = link_data.get("last_seen_character_id", 0)
            try:
                last_seen_character_id = int(raw_last_seen or 0)
            except (TypeError, ValueError):
                last_seen_character_id = 0
            if last_seen_character_id < 0:
                last_seen_character_id = 0

            links[token] = {
                "user_id": parsed_user_id,
                "created_at": str(link_data.get("created_at", "")),
                "last_used_at": str(link_data.get("last_used_at", "")),
                "auto_bind_next_seen_character": bool(link_data.get("auto_bind_next_seen_character", False)),
                "last_seen_character_id": last_seen_character_id,
                "character_bindings": {},
                "seasonal_character_ids": [],
                "character_metadata": {},
            }

            raw_bindings = link_data.get("character_bindings", {})
            if isinstance(raw_bindings, dict):
                bindings: Dict[str, int] = {}
                for raw_character_id, raw_ppe_id in raw_bindings.items():
                    try:
                        character_id = int(raw_character_id)
                        ppe_id = int(raw_ppe_id)
                    except (TypeError, ValueError):
                        continue
                    if character_id <= 0 or ppe_id <= 0:
                        continue
                    bindings[str(character_id)] = ppe_id
                links[token]["character_bindings"] = bindings

            raw_seasonal_ids = link_data.get("seasonal_character_ids", [])
            seasonal_ids = raw_seasonal_ids if isinstance(raw_seasonal_ids, list) else []
            normalized_seasonal_ids: list[str] = []
            for raw_character_id in seasonal_ids:
                try:
                    character_id = int(raw_character_id)
                except (TypeError, ValueError):
                    continue
                if character_id <= 0:
                    continue
                normalized_seasonal_ids.append(str(character_id))
            links[token]["seasonal_character_ids"] = sorted(set(normalized_seasonal_ids), key=int)

            raw_metadata = link_data.get("character_metadata", {})
            metadata: Dict[str, Dict[str, str]] = {}
            if isinstance(raw_metadata, dict):
                for raw_character_id, raw_entry in raw_metadata.items():
                    try:
                        character_id = int(raw_character_id)
                    except (TypeError, ValueError):
                        continue
                    if character_id <= 0 or not isinstance(raw_entry, dict):
                        continue

                    metadata[str(character_id)] = {
                        "character_name": str(raw_entry.get("character_name", "")),
                        "character_class": str(raw_entry.get("character_class", "")),
                    }
            links[token]["character_metadata"] = metadata

    announce_channel_raw = settings.get("announce_channel_id", _DEFAULT_CONFIG["realmshark_settings"]["announce_channel_id"])
    try:
        announce_channel_id = int(announce_channel_raw)
    except (TypeError, ValueError):
        announce_channel_id = _DEFAULT_CONFIG["realmshark_settings"]["announce_channel_id"]

    if announce_channel_id < 0:
        announce_channel_id = _DEFAULT_CONFIG["realmshark_settings"]["announce_channel_id"]

    return {
        "enabled": bool(settings.get("enabled", _DEFAULT_CONFIG["realmshark_settings"]["enabled"])),
        "mode": mode,
        "links": links,
        "announce_channel_id": announce_channel_id,
    }


def _merge_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(_DEFAULT_CONFIG)
    merged["quest_settings"] = _normalized_targets(raw)
    merged["realmshark_settings"] = _normalized_realmshark_settings(raw)
    return merged


async def load_guild_config_by_id(guild_id: int) -> Dict[str, Any]:
    path = _config_path(guild_id)

    if not os.path.exists(path):
        config = _merge_defaults({})
        async with get_lock(guild_id):
            await asyncio.to_thread(_write_json_atomic, path, config)
        return config

    async with get_lock(guild_id):
        raw = await asyncio.to_thread(_read_json, path)
        normalized = _merge_defaults(raw)
        if normalized != raw:
            await asyncio.to_thread(_write_json_atomic, path, normalized)
        return normalized


async def save_guild_config_by_id(guild_id: int, config: Dict[str, Any]) -> Dict[str, Any]:
    path = _config_path(guild_id)
    normalized = _merge_defaults(config)

    async with get_lock(guild_id):
        await asyncio.to_thread(_write_json_atomic, path, normalized)

    return normalized


async def load_guild_config(interaction: discord.Interaction) -> Dict[str, Any]:
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")

    guild_id = interaction.guild.id
    return await load_guild_config_by_id(guild_id)


async def save_guild_config(interaction: discord.Interaction, config: Dict[str, Any]) -> Dict[str, Any]:
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")

    guild_id = interaction.guild.id
    return await save_guild_config_by_id(guild_id, config)


async def get_quest_targets(interaction: discord.Interaction) -> tuple[int, int, int]:
    config = await load_guild_config(interaction)
    settings = config["quest_settings"]
    return settings["regular_target"], settings["shiny_target"], settings["skin_target"]


async def set_quest_targets(
    interaction: discord.Interaction,
    *,
    regular_target: int | None = None,
    shiny_target: int | None = None,
    skin_target: int | None = None,
) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    settings = dict(config.get("quest_settings", {}))

    if regular_target is not None:
        settings["regular_target"] = max(0, int(regular_target))
    if shiny_target is not None:
        settings["shiny_target"] = max(0, int(shiny_target))
    if skin_target is not None:
        settings["skin_target"] = max(0, int(skin_target))

    config["quest_settings"] = settings
    return await save_guild_config(interaction, config)


async def get_quest_points(interaction: discord.Interaction) -> tuple[int, int, int]:
    config = await load_guild_config(interaction)
    settings = config["quest_settings"]
    return settings["regular_points"], settings["shiny_points"], settings["skin_points"]


async def set_quest_points(
    interaction: discord.Interaction,
    *,
    regular_points: int | None = None,
    shiny_points: int | None = None,
    skin_points: int | None = None,
) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    settings = dict(config.get("quest_settings", {}))

    if regular_points is not None:
        settings["regular_points"] = max(0, int(regular_points))
    if shiny_points is not None:
        settings["shiny_points"] = max(0, int(shiny_points))
    if skin_points is not None:
        settings["skin_points"] = max(0, int(skin_points))

    config["quest_settings"] = settings
    return await save_guild_config(interaction, config)


async def get_realmshark_settings(interaction: discord.Interaction) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    return dict(config["realmshark_settings"])


async def set_realmshark_settings(interaction: discord.Interaction, settings: Dict[str, Any]) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    config["realmshark_settings"] = settings
    saved = await save_guild_config(interaction, config)
    return dict(saved["realmshark_settings"])


async def get_realmshark_settings_by_id(guild_id: int) -> Dict[str, Any]:
    config = await load_guild_config_by_id(guild_id)
    return dict(config["realmshark_settings"])


async def set_realmshark_settings_by_id(guild_id: int, settings: Dict[str, Any]) -> Dict[str, Any]:
    config = await load_guild_config_by_id(guild_id)
    config["realmshark_settings"] = settings
    saved = await save_guild_config_by_id(guild_id, config)
    return dict(saved["realmshark_settings"])
