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
    }
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


def _merge_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(_DEFAULT_CONFIG)
    merged["quest_settings"] = _normalized_targets(raw)
    return merged


async def load_guild_config(interaction: discord.Interaction) -> Dict[str, Any]:
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")

    guild_id = interaction.guild.id
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


async def save_guild_config(interaction: discord.Interaction, config: Dict[str, Any]) -> Dict[str, Any]:
    if interaction.guild is None:
        raise ValueError("Interaction guild is None.")

    guild_id = interaction.guild.id
    path = _config_path(guild_id)
    normalized = _merge_defaults(config)

    async with get_lock(guild_id):
        await asyncio.to_thread(_write_json_atomic, path, normalized)

    return normalized


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
