"""Utilities for guild config."""

import asyncio
import json
import os
from typing import Any, Dict

import discord

from utils.ppe_types import (
    all_ppe_types,
    normalize_cleared_combo_signatures,
    normalize_allowed_ppe_types,
    normalize_combo_signature,
    normalize_iterative_combo_overrides,
    normalize_iterative_option_multipliers,
    normalize_ppe_combo_label_overrides,
    normalize_ppe_type_label_overrides,
    normalize_ppe_type_multipliers,
    normalize_ppe_type_short_label_overrides,
)

from utils.player_records import DATA_DIR, get_lock
from utils.contest_leaderboards import normalize_contest_leaderboard_id

DEFAULT_MAX_PPE_CHARACTERS = 10

_DEFAULT_CONFIG: Dict[str, Any] = {
    "ppe_settings": {
        "max_ppes": DEFAULT_MAX_PPE_CHARACTERS,
        "enable_ppe_types": True,
        "allowed_ppe_types": all_ppe_types(),
        "ppe_type_multipliers": normalize_ppe_type_multipliers({}),
        "iterative_base_multipliers": normalize_iterative_option_multipliers({}),
        "iterative_combo_overrides": normalize_iterative_combo_overrides({}),
        "iterative_cleared_signatures": normalize_cleared_combo_signatures([]),
        "type_label_overrides": normalize_ppe_type_label_overrides({}),
        "type_short_label_overrides": normalize_ppe_type_short_label_overrides({}),
        "combo_label_overrides": normalize_ppe_combo_label_overrides({}),
    },
    "quest_settings": {
        "regular_target": 8,
        "shiny_target": 3,
        "skin_target": 1,
        "regular_points": 5,
        "shiny_points": 10,
        "skin_points": 15,
        "num_resets": 3,
        "use_global_quests": False,
        "enable_team_quests": False,
        "global_regular_quests": [],
        "global_shiny_quests": [],
        "global_skin_quests": [],
        "team_quests_state": {},
    },
    "realmshark_settings": {
        "enabled": False,
        "mode": "addloot",
        "links": {},
        "announce_channel_id": 0,
        "endpoint": "",
    },
    "contest_settings": {
        "default_contest_leaderboard": None,
        "ppe_aggregate_points_enabled": False,
        "ppe_contest_include_quest_points": False,
        "ppe_contest_require_active_ppe_quest_items": True,
        "team_aggregate_points_enabled": False,
        "team_contest_include_quest_points": False,
        "join_contest_channel_id": 0,
        "join_contest_message_id": 0,
        "join_contest_emoji": "✅",
    },
    "points_settings": {
        "global": {
            "loot_percent": 0.0,
            "bonus_percent": 0.0,
            "penalty_percent": 0.0,
            "total_percent": 0.0,
        },
        "tops_point_mode": "current",
        "rarity_multipliers": {
            "common": 1.0,
            "uncommon": 1.0,
            "rare": 1.0,
            "legendary": 1.0,
            "divine": 2.0,
            "shiny": 2.0,
        },
        "starting_penalty_modifiers": {
            "pet_level_percent_reduction": 0.0,
            "exalts_percent_reduction": 0.0,
            "loot_percent_reduction": 0.0,
            "incombat_percent_reduction": 0.0,
        },
        "duplicate_point_reduction": 0.5,
        "duplicate_match_mode": "separate_rarity",
        "penalty_weights": {
            "pet_level_per_point": 4.0,
            "exalts_per_point": 2.0,
            "loot_percent_per_point": 0.5,
            "incombat_seconds_per_point": 0.1,
        },
        "class_overrides": {},
        "set_overrides": {
            "ST": {},
            "UT": {},
        },
        "default_ut_points": 0.0,
        "default_st_points": 0.0,
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


def _normalized_targets(config: Dict[str, Any]) -> Dict[str, Any]:
    settings = config.get("quest_settings", {}) if isinstance(config.get("quest_settings", {}), dict) else {}

    def _as_non_negative_int(value: Any, fallback: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(0, parsed)

    def _as_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            text = entry.strip()
            if text:
                normalized.append(text)
        return normalized

    def _as_team_quest_state_map(value: Any) -> dict[str, dict[str, list[str]]]:
        if not isinstance(value, dict):
            return {}

        output: dict[str, dict[str, list[str]]] = {}
        for raw_team_name, raw_state in value.items():
            if not isinstance(raw_team_name, str):
                continue
            team_name = raw_team_name.strip().lower()
            if not team_name or not isinstance(raw_state, dict):
                continue
            output[team_name] = {
                "current_items": _as_string_list(raw_state.get("current_items")),
                "current_shinies": _as_string_list(raw_state.get("current_shinies")),
                "current_skins": _as_string_list(raw_state.get("current_skins")),
                "completed_items": _as_string_list(raw_state.get("completed_items")),
                "completed_shinies": _as_string_list(raw_state.get("completed_shinies")),
                "completed_skins": _as_string_list(raw_state.get("completed_skins")),
            }
        return output

    return {
        "regular_target": _as_non_negative_int(settings.get("regular_target"), _DEFAULT_CONFIG["quest_settings"]["regular_target"]),
        "shiny_target": _as_non_negative_int(settings.get("shiny_target"), _DEFAULT_CONFIG["quest_settings"]["shiny_target"]),
        "skin_target": _as_non_negative_int(settings.get("skin_target"), _DEFAULT_CONFIG["quest_settings"]["skin_target"]),
        "regular_points": _as_non_negative_int(settings.get("regular_points"), _DEFAULT_CONFIG["quest_settings"]["regular_points"]),
        "shiny_points": _as_non_negative_int(settings.get("shiny_points"), _DEFAULT_CONFIG["quest_settings"]["shiny_points"]),
        "skin_points": _as_non_negative_int(settings.get("skin_points"), _DEFAULT_CONFIG["quest_settings"]["skin_points"]),
        "num_resets": _as_non_negative_int(settings.get("num_resets"), _DEFAULT_CONFIG["quest_settings"]["num_resets"]),
        "use_global_quests": bool(settings.get("use_global_quests", _DEFAULT_CONFIG["quest_settings"]["use_global_quests"])),
        "enable_team_quests": bool(settings.get("enable_team_quests", _DEFAULT_CONFIG["quest_settings"]["enable_team_quests"])),
        "global_regular_quests": _as_string_list(settings.get("global_regular_quests")),
        "global_shiny_quests": _as_string_list(settings.get("global_shiny_quests")),
        "global_skin_quests": _as_string_list(settings.get("global_skin_quests")),
        "team_quests_state": _as_team_quest_state_map(settings.get("team_quests_state")),
    }


def _normalized_ppe_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    settings = config.get("ppe_settings", {}) if isinstance(config.get("ppe_settings", {}), dict) else {}

    try:
        parsed_max = int(settings.get("max_ppes", _DEFAULT_CONFIG["ppe_settings"]["max_ppes"]))
    except (TypeError, ValueError):
        parsed_max = _DEFAULT_CONFIG["ppe_settings"]["max_ppes"]

    if parsed_max <= 0:
        parsed_max = _DEFAULT_CONFIG["ppe_settings"]["max_ppes"]

    allowed_types = normalize_allowed_ppe_types(settings.get("allowed_ppe_types"))
    multipliers = normalize_ppe_type_multipliers(settings.get("ppe_type_multipliers"))
    iterative_base_multipliers = normalize_iterative_option_multipliers(settings.get("iterative_base_multipliers"))
    iterative_combo_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
    iterative_cleared_signatures = normalize_cleared_combo_signatures(settings.get("iterative_cleared_signatures"))
    type_label_overrides = normalize_ppe_type_label_overrides(settings.get("type_label_overrides"))
    type_short_label_overrides = normalize_ppe_type_short_label_overrides(settings.get("type_short_label_overrides"))
    combo_label_overrides = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))

    return {
        "max_ppes": parsed_max,
        "enable_ppe_types": bool(settings.get("enable_ppe_types", True)),
        "allowed_ppe_types": allowed_types,
        "ppe_type_multipliers": multipliers,
        "iterative_base_multipliers": iterative_base_multipliers,
        "iterative_combo_overrides": iterative_combo_overrides,
        "iterative_cleared_signatures": iterative_cleared_signatures,
        "type_label_overrides": type_label_overrides,
        "type_short_label_overrides": type_short_label_overrides,
        "combo_label_overrides": combo_label_overrides,
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

    endpoint_raw = settings.get("endpoint", _DEFAULT_CONFIG["realmshark_settings"]["endpoint"])
    endpoint = endpoint_raw.strip() if isinstance(endpoint_raw, str) else ""

    return {
        "enabled": bool(settings.get("enabled", _DEFAULT_CONFIG["realmshark_settings"]["enabled"])),
        "mode": mode,
        "links": links,
        "announce_channel_id": announce_channel_id,
        "endpoint": endpoint,
    }


def _merge_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(_DEFAULT_CONFIG)
    merged["ppe_settings"] = _normalized_ppe_settings(raw)
    merged["quest_settings"] = _normalized_targets(raw)
    merged["realmshark_settings"] = _normalized_realmshark_settings(raw)
    merged["contest_settings"] = _normalized_contest_settings(raw)
    merged["points_settings"] = _normalized_points_settings(raw)
    return merged


def _normalized_contest_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    settings = config.get("contest_settings", {}) if isinstance(config.get("contest_settings", {}), dict) else {}

    def _as_non_negative_int(value: Any, fallback: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed >= 0 else fallback

    join_embed_emoji_raw = settings.get("join_contest_emoji", "✅")
    join_embed_emoji = join_embed_emoji_raw.strip() if isinstance(join_embed_emoji_raw, str) else "✅"
    if not join_embed_emoji:
        join_embed_emoji = "✅"

    default_choice = normalize_contest_leaderboard_id(settings.get("default_contest_leaderboard"))
    return {
        "default_contest_leaderboard": default_choice,
        "ppe_aggregate_points_enabled": bool(
            settings.get(
                "ppe_aggregate_points_enabled",
                _DEFAULT_CONFIG["contest_settings"]["ppe_aggregate_points_enabled"],
            )
        ),
        "ppe_contest_include_quest_points": bool(
            settings.get(
                "ppe_contest_include_quest_points",
                _DEFAULT_CONFIG["contest_settings"]["ppe_contest_include_quest_points"],
            )
        ),
        "ppe_contest_require_active_ppe_quest_items": bool(
            settings.get(
                "ppe_contest_require_active_ppe_quest_items",
                _DEFAULT_CONFIG["contest_settings"]["ppe_contest_require_active_ppe_quest_items"],
            )
        ),
        "team_aggregate_points_enabled": bool(
            settings.get(
                "team_aggregate_points_enabled",
                _DEFAULT_CONFIG["contest_settings"]["team_aggregate_points_enabled"],
            )
        ),
        "team_contest_include_quest_points": bool(
            settings.get(
                "team_contest_include_quest_points",
                _DEFAULT_CONFIG["contest_settings"]["team_contest_include_quest_points"],
            )
        ),
        "join_contest_channel_id": _as_non_negative_int(settings.get("join_contest_channel_id", 0), 0),
        "join_contest_message_id": _as_non_negative_int(settings.get("join_contest_message_id", 0), 0),
        "join_contest_emoji": join_embed_emoji,
    }


def _normalized_points_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    raw = config.get("points_settings", {}) if isinstance(config.get("points_settings", {}), dict) else {}
    raw_global = raw.get("global", {}) if isinstance(raw.get("global", {}), dict) else {}
    raw_starting_penalty_modifiers = (
        raw.get("starting_penalty_modifiers", {}) if isinstance(raw.get("starting_penalty_modifiers", {}), dict) else {}
    )

    def _normalize_tops_point_mode(value: Any) -> str:
        mode = str(value).strip().lower()
        if mode in {"current", "once", "none"}:
            return mode
        return _DEFAULT_CONFIG["points_settings"]["tops_point_mode"]

    def _as_float(value: Any, fallback: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    normalized_global = {
        "loot_percent": _as_float(raw_global.get("loot_percent"), _DEFAULT_CONFIG["points_settings"]["global"]["loot_percent"]),
        "bonus_percent": _as_float(raw_global.get("bonus_percent"), _DEFAULT_CONFIG["points_settings"]["global"]["bonus_percent"]),
        "penalty_percent": _as_float(raw_global.get("penalty_percent"), _DEFAULT_CONFIG["points_settings"]["global"]["penalty_percent"]),
        "total_percent": _as_float(raw_global.get("total_percent"), _DEFAULT_CONFIG["points_settings"]["global"]["total_percent"]),
    }

    raw_rarity_multipliers = raw.get("rarity_multipliers", {}) if isinstance(raw.get("rarity_multipliers", {}), dict) else {}
    normalized_rarity_multipliers = {
        "common": max(0.0, _as_float(raw_rarity_multipliers.get("common"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["common"])),
        "uncommon": max(0.0, _as_float(raw_rarity_multipliers.get("uncommon"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["uncommon"])),
        "rare": max(0.0, _as_float(raw_rarity_multipliers.get("rare"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["rare"])),
        "legendary": max(0.0, _as_float(raw_rarity_multipliers.get("legendary"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["legendary"])),
        "divine": max(0.0, _as_float(raw_rarity_multipliers.get("divine"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["divine"])),
        "shiny": max(0.0, _as_float(raw_rarity_multipliers.get("shiny"), _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]["shiny"])),
    }

    duplicate_match_mode = str(raw.get("duplicate_match_mode", _DEFAULT_CONFIG["points_settings"]["duplicate_match_mode"]))
    duplicate_match_mode = duplicate_match_mode.strip().lower()
    if duplicate_match_mode not in {"separate_rarity", "any_rarity", "non_divine_any_rarity", "all_including_shiny"}:
        duplicate_match_mode = _DEFAULT_CONFIG["points_settings"]["duplicate_match_mode"]

    normalized_starting_penalty_modifiers = {
        "pet_level_percent_reduction": max(0.0, _as_float(raw_starting_penalty_modifiers.get("pet_level_percent_reduction"), 0.0)),
        "exalts_percent_reduction": max(0.0, _as_float(raw_starting_penalty_modifiers.get("exalts_percent_reduction"), 0.0)),
        "loot_percent_reduction": max(0.0, _as_float(raw_starting_penalty_modifiers.get("loot_percent_reduction"), 0.0)),
        "incombat_percent_reduction": max(0.0, _as_float(raw_starting_penalty_modifiers.get("incombat_percent_reduction"), 0.0)),
    }

    duplicate_point_reduction = _as_float(
        raw.get("duplicate_point_reduction"),
        _DEFAULT_CONFIG["points_settings"]["duplicate_point_reduction"],
    )
    if duplicate_point_reduction < 0:
        duplicate_point_reduction = _DEFAULT_CONFIG["points_settings"]["duplicate_point_reduction"]

    raw_penalty_weights = raw.get("penalty_weights", {}) if isinstance(raw.get("penalty_weights", {}), dict) else {}

    def _non_negative_float(value: Any, fallback: float) -> float:
        parsed = _as_float(value, fallback)
        return parsed if parsed >= 0 else fallback

    normalized_penalty_weights = {
        "pet_level_per_point": _non_negative_float(
            raw_penalty_weights.get("pet_level_per_point"),
            _DEFAULT_CONFIG["points_settings"]["penalty_weights"]["pet_level_per_point"],
        ),
        "exalts_per_point": _non_negative_float(
            raw_penalty_weights.get("exalts_per_point"),
            _DEFAULT_CONFIG["points_settings"]["penalty_weights"]["exalts_per_point"],
        ),
        "loot_percent_per_point": _non_negative_float(
            raw_penalty_weights.get("loot_percent_per_point"),
            _DEFAULT_CONFIG["points_settings"]["penalty_weights"]["loot_percent_per_point"],
        ),
        "incombat_seconds_per_point": _non_negative_float(
            raw_penalty_weights.get("incombat_seconds_per_point"),
            _DEFAULT_CONFIG["points_settings"]["penalty_weights"]["incombat_seconds_per_point"],
        ),
    }

    normalized_overrides: Dict[str, Dict[str, Any]] = {}
    class_overrides = raw.get("class_overrides", {})
    if isinstance(class_overrides, dict):
        for class_name, override in class_overrides.items():
            if not isinstance(class_name, str) or not isinstance(override, dict):
                continue

            minimum_total = override.get("minimum_total")
            if minimum_total is not None:
                minimum_total = _as_float(minimum_total, 0.0)

            normalized_overrides[class_name] = {
                "loot_percent": _as_float(override.get("loot_percent"), 0.0),
                "bonus_percent": _as_float(override.get("bonus_percent"), 0.0),
                "penalty_percent": _as_float(override.get("penalty_percent"), 0.0),
                "total_percent": _as_float(override.get("total_percent"), 0.0),
                "minimum_total": minimum_total,
            }

    default_ut_points = max(
        0.0,
        _as_float(raw.get("default_ut_points"), _DEFAULT_CONFIG["points_settings"]["default_ut_points"]),
    )
    default_st_points = max(
        0.0,
        _as_float(raw.get("default_st_points"), _DEFAULT_CONFIG["points_settings"]["default_st_points"]),
    )

    raw_set_overrides = raw.get("set_overrides", {}) if isinstance(raw.get("set_overrides", {}), dict) else {}

    normalized_set_overrides: Dict[str, Dict[str, float]] = {"UT": {}, "ST": {}}
    for set_type in ("UT", "ST"):
        type_bucket = raw_set_overrides.get(set_type, {}) if isinstance(raw_set_overrides.get(set_type, {}), dict) else {}
        for set_name, points in type_bucket.items():
            if not isinstance(set_name, str) or not set_name:
                continue
            parsed_points = _as_float(points, 0.0)
            if parsed_points < 0:
                continue
            baseline = default_ut_points if set_type == "UT" else default_st_points
            if parsed_points == baseline:
                continue
            normalized_set_overrides[set_type][set_name] = parsed_points

    return {
        "global": normalized_global,
        "tops_point_mode": _normalize_tops_point_mode(raw.get("tops_point_mode", _DEFAULT_CONFIG["points_settings"]["tops_point_mode"])),
        "rarity_multipliers": normalized_rarity_multipliers,
        "starting_penalty_modifiers": normalized_starting_penalty_modifiers,
        "duplicate_point_reduction": duplicate_point_reduction,
        "duplicate_match_mode": duplicate_match_mode,
        "penalty_weights": normalized_penalty_weights,
        "class_overrides": normalized_overrides,
        "set_overrides": normalized_set_overrides,
        "default_ut_points": default_ut_points,
        "default_st_points": default_st_points,
    }


def get_rarity_multipliers(guild_config: Dict[str, Any] | None) -> Dict[str, float]:
    points_settings = guild_config.get("points_settings", {}) if isinstance(guild_config, dict) else {}
    raw_multipliers = points_settings.get("rarity_multipliers", {}) if isinstance(points_settings.get("rarity_multipliers", {}), dict) else {}
    defaults = _DEFAULT_CONFIG["points_settings"]["rarity_multipliers"]
    result: Dict[str, float] = {}
    for rarity, fallback in defaults.items():
        try:
            parsed = float(raw_multipliers.get(rarity, fallback))
        except (TypeError, ValueError):
            parsed = float(fallback)
        result[rarity] = parsed if parsed >= 0 else float(fallback)

    if "shiny" not in result:
        result["shiny"] = float(defaults.get("shiny", 2.0))

    return result


def get_set_bonuses(guild_config: Dict[str, Any] | None) -> Dict[str, Dict[str, float]]:
    """Return effective set points map using defaults + explicit overrides."""
    points_settings = guild_config.get("points_settings", {}) if isinstance(guild_config, dict) else {}
    raw_overrides = points_settings.get("set_overrides", {}) if isinstance(points_settings.get("set_overrides", {}), dict) else {}

    try:
        default_ut = max(0.0, float(points_settings.get("default_ut_points", 0.0)))
    except (TypeError, ValueError):
        default_ut = 0.0
    try:
        default_st = max(0.0, float(points_settings.get("default_st_points", 0.0)))
    except (TypeError, ValueError):
        default_st = 0.0

    from utils.set_operations import load_item_sets

    all_sets = load_item_sets()
    result: Dict[str, Dict[str, float]] = {"UT": {}, "ST": {}}
    for set_name, set_data in all_sets.items():
        set_type = str(set_data.get("type", "")).upper()
        if set_type not in {"UT", "ST"}:
            continue

        base_points = default_ut if set_type == "UT" else default_st
        points = base_points

        type_overrides = raw_overrides.get(set_type, {}) if isinstance(raw_overrides.get(set_type, {}), dict) else {}
        if set_name in type_overrides:
            try:
                parsed = float(type_overrides[set_name])
                if parsed >= 0:
                    points = parsed
            except (TypeError, ValueError):
                pass

        result[set_type][set_name] = points
    return result


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


async def get_max_ppes(interaction: discord.Interaction) -> int:
    config = await load_guild_config(interaction)
    settings = config["ppe_settings"]
    return int(settings["max_ppes"])


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


async def set_max_ppes(interaction: discord.Interaction, *, max_ppes: int) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    settings = dict(config.get("ppe_settings", {}))
    settings["max_ppes"] = max(1, int(max_ppes))
    config["ppe_settings"] = settings
    return await save_guild_config(interaction, config)


async def get_ppe_settings(interaction: discord.Interaction) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    return dict(config["ppe_settings"])


async def set_ppe_settings(interaction: discord.Interaction, settings: Dict[str, Any]) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    config["ppe_settings"] = settings
    saved = await save_guild_config(interaction, config)
    return dict(saved["ppe_settings"])


async def update_iterative_ppe_option_multipliers(
    interaction: discord.Interaction,
    *,
    multipliers: Dict[str, Any],
) -> Dict[str, Any]:
    settings = await get_ppe_settings(interaction)
    settings["iterative_base_multipliers"] = normalize_iterative_option_multipliers(multipliers)
    return await set_ppe_settings(interaction, settings)


async def update_iterative_ppe_combo_overrides(
    interaction: discord.Interaction,
    *,
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    settings = await get_ppe_settings(interaction)
    settings["iterative_combo_overrides"] = normalize_iterative_combo_overrides(overrides)
    return await set_ppe_settings(interaction, settings)


async def set_iterative_ppe_combo_override(
    interaction: discord.Interaction,
    *,
    signature: str,
    multiplier: float | None,
) -> Dict[str, Any]:
    settings = await get_ppe_settings(interaction)
    current = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
    cleared_signatures = set(normalize_cleared_combo_signatures(settings.get("iterative_cleared_signatures")))
    normalized_signature = normalize_combo_signature(signature)
    if normalized_signature:
        if multiplier is None:
            current.pop(normalized_signature, None)
            cleared_signatures.add(normalized_signature)
        elif float(multiplier) > 0:
            current[normalized_signature] = float(multiplier)
            cleared_signatures.discard(normalized_signature)
    settings["iterative_combo_overrides"] = current
    settings["iterative_cleared_signatures"] = sorted(cleared_signatures)
    return await set_ppe_settings(interaction, settings)


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


async def get_contest_settings(interaction: discord.Interaction) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    return dict(config["contest_settings"])


async def set_contest_settings(interaction: discord.Interaction, settings: Dict[str, Any]) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    config["contest_settings"] = settings
    saved = await save_guild_config(interaction, config)
    return dict(saved["contest_settings"])


async def get_points_settings(interaction: discord.Interaction) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    return dict(config["points_settings"])


async def set_points_settings(interaction: discord.Interaction, settings: Dict[str, Any]) -> Dict[str, Any]:
    config = await load_guild_config(interaction)
    config["points_settings"] = settings
    saved = await save_guild_config(interaction, config)
    return dict(saved["points_settings"])


async def update_global_points_modifiers(
    interaction: discord.Interaction,
    *,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
    duplicate_point_reduction: float | None = None,
) -> Dict[str, Any]:
    settings = await get_points_settings(interaction)
    global_settings = dict(settings.get("global", {}))

    if loot_percent is not None:
        global_settings["loot_percent"] = float(loot_percent)
    if bonus_percent is not None:
        global_settings["bonus_percent"] = float(bonus_percent)
    if penalty_percent is not None:
        global_settings["penalty_percent"] = float(penalty_percent)
    if total_percent is not None:
        global_settings["total_percent"] = float(total_percent)
    if duplicate_point_reduction is not None:
        settings["duplicate_point_reduction"] = max(0.0, float(duplicate_point_reduction))

    settings["global"] = global_settings
    return await set_points_settings(interaction, settings)


async def update_starting_penalty_modifiers(
    interaction: discord.Interaction,
    *,
    pet_level_percent_reduction: float | None = None,
    exalts_percent_reduction: float | None = None,
    loot_percent_reduction: float | None = None,
    incombat_percent_reduction: float | None = None,
) -> Dict[str, Any]:
    settings = await get_points_settings(interaction)
    modifier_settings = dict(settings.get("starting_penalty_modifiers", {}))

    if pet_level_percent_reduction is not None:
        modifier_settings["pet_level_percent_reduction"] = max(0.0, float(pet_level_percent_reduction))
    if exalts_percent_reduction is not None:
        modifier_settings["exalts_percent_reduction"] = max(0.0, float(exalts_percent_reduction))
    if loot_percent_reduction is not None:
        modifier_settings["loot_percent_reduction"] = max(0.0, float(loot_percent_reduction))
    if incombat_percent_reduction is not None:
        modifier_settings["incombat_percent_reduction"] = max(0.0, float(incombat_percent_reduction))

    settings["starting_penalty_modifiers"] = modifier_settings
    return await set_points_settings(interaction, settings)


async def update_class_points_modifiers(
    interaction: discord.Interaction,
    *,
    class_name: str,
    loot_percent: float | None = None,
    bonus_percent: float | None = None,
    penalty_percent: float | None = None,
    total_percent: float | None = None,
    minimum_total: float | None = None,
) -> Dict[str, Any]:
    settings = await get_points_settings(interaction)
    class_overrides = dict(settings.get("class_overrides", {}))
    override = dict(class_overrides.get(class_name, {}))

    if loot_percent is not None:
        override["loot_percent"] = float(loot_percent)
    if bonus_percent is not None:
        override["bonus_percent"] = float(bonus_percent)
    if penalty_percent is not None:
        override["penalty_percent"] = float(penalty_percent)
    if total_percent is not None:
        override["total_percent"] = float(total_percent)
    if minimum_total is not None:
        override["minimum_total"] = float(minimum_total)

    if not override:
        class_overrides.pop(class_name, None)
    else:
        override.setdefault("loot_percent", 0.0)
        override.setdefault("bonus_percent", 0.0)
        override.setdefault("penalty_percent", 0.0)
        override.setdefault("total_percent", 0.0)
        override.setdefault("minimum_total", None)
        class_overrides[class_name] = override

    settings["class_overrides"] = class_overrides
    return await set_points_settings(interaction, settings)
