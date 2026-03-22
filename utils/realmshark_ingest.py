from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
from typing import Any, Awaitable, Callable, Dict

from dataclass import PlayerData
from utils.calc_points import calc_points, load_loot_points, normalize_item_name
from utils.guild_config import get_quest_targets, get_realmshark_settings_by_id, set_realmshark_settings_by_id
from utils.loot_data import LOOT
from utils.player_manager import player_manager
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.quest_manager import update_quests_for_item


class IngestValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "bad_request") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class _SyntheticGuild:
    id: int


@dataclass
class _SyntheticUser:
    id: int


@dataclass
class _SyntheticInteraction:
    guild: _SyntheticGuild
    user: _SyntheticUser


_DEBUG = os.getenv("REALMSHARK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
_MISSING_ITEMS_LOG_PATH = "/data/realmshark_not_logged_items.jsonl"
Notifier = Callable[[int, str], Awaitable[None]]


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _debug_log(message: str) -> None:
    if _DEBUG:
        print(f"[REALMSHARK_DEBUG] {message}")


def _is_known_csv_item(raw_item_name: str) -> str | None:
    normalized = normalize_item_name(raw_item_name).lower()
    if not normalized:
        return None

    for known_item in LOOT:
        if normalize_item_name(known_item).lower() == normalized:
            return known_item
    return None


def _is_ut_or_st_event(payload: Dict[str, Any]) -> bool:
    if _as_bool(payload.get("is_ut_or_st", False)):
        return True

    group = str(payload.get("item_group", "")).upper()
    label = str(payload.get("item_label", "")).upper()
    marker = f"{group} {label}"
    tokens = {token for token in re.split(r"[^A-Z0-9]+", marker) if token}
    return "UT" in tokens or "ST" in tokens


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0

    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _append_missing_utst_log(guild_id: int, item_name: str, payload: Dict[str, Any]) -> None:
    # Avoid persisting link tokens in plaintext audit files.
    payload_safe = dict(payload)
    if "link_token" in payload_safe:
        payload_safe["link_token"] = "[REDACTED]"

    entry = {
        "ts": _utc_iso_now(),
        "guild_id": guild_id,
        "item_name": item_name,
        "reason": "ut_or_st_missing_from_rotmg_loot_drops_updated",
        "payload": payload_safe,
    }

    os.makedirs(os.path.dirname(_MISSING_ITEMS_LOG_PATH), exist_ok=True)
    with open(_MISSING_ITEMS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    _debug_log(f"Flagged missing UT/ST item for CSV follow-up: item={item_name} guild={guild_id}")


def _resolve_item_name(raw_item_name: str) -> str:
    known_item = _is_known_csv_item(raw_item_name)
    if known_item is None:
        normalized = normalize_item_name(raw_item_name).lower()
        if not normalized:
            raise IngestValidationError("item_name is required.", status_code=400, error_code="missing_item")

        raise IngestValidationError(
            f"'{raw_item_name}' is not a recognized item name.",
            status_code=400,
            error_code="invalid_item",
        )

    return known_item


def _resolve_known_item_if_any(raw_item_name: str) -> str | None:
    known_item = _is_known_csv_item(raw_item_name)
    if known_item is not None:
        return known_item

    normalized = normalize_item_name(raw_item_name).lower()
    if not normalized:
        raise IngestValidationError("item_name is required.", status_code=400, error_code="missing_item")
    return None


def _validate_shiny_variant(item_name: str, shiny: bool) -> None:
    if not shiny:
        return

    loot_points = load_loot_points()
    shiny_item_name = f"{item_name} (shiny)"
    if shiny_item_name not in loot_points:
        raise IngestValidationError(
            f"Shiny variant of '{item_name}' is not currently supported.",
            status_code=400,
            error_code="invalid_shiny_variant",
        )


async def _addloot_for_user(guild_id: int, user_id: int, item_name: str, divine: bool, shiny: bool) -> Dict[str, Any]:
    interaction = _SyntheticInteraction(guild=_SyntheticGuild(guild_id), user=_SyntheticUser(user_id))

    points = calc_points(item_name, divine, shiny)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records.get(key)

    if player_data is None or not player_data.is_member:
        raise IngestValidationError("Linked user is not part of the PPE contest.", status_code=403, error_code="not_member")

    ppe_id = player_data.active_ppe
    if ppe_id is None:
        raise IngestValidationError("Linked user does not have an active PPE.", status_code=409, error_code="no_active_ppe")

    item_key, points_added, active_ppe, _quest_update = await player_manager.add_loot_and_points(
        interaction,
        user=_SyntheticUser(user_id),
        ppe_id=ppe_id,
        item_name=item_name,
        divine=divine,
        shiny=shiny,
        points=points,
    )

    return {
        "mode": "addloot",
        "item": item_key,
        "points_added": points_added,
        "total_points": active_ppe.points,
        "ppe_id": active_ppe.id,
    }


async def _addseasonloot_for_user(guild_id: int, user_id: int, item_name: str, shiny: bool) -> Dict[str, Any]:
    interaction = _SyntheticInteraction(guild=_SyntheticGuild(guild_id), user=_SyntheticUser(user_id))

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)

    player_data: PlayerData | None = records.get(key)
    if player_data is None or not player_data.is_member:
        raise IngestValidationError("Linked user is not part of the PPE contest.", status_code=403, error_code="not_member")

    item_key = (item_name, shiny)
    if item_key in player_data.unique_items:
        raise IngestValidationError(
            f"'{item_name}{' (shiny)' if shiny else ''}' is already in season loot.",
            status_code=409,
            error_code="duplicate_season_item",
        )

    player_data.unique_items.add(item_key)
    regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
    update_quests_for_item(
        player_data,
        item_name,
        shiny,
        target_item_quests=regular_target,
        target_shiny_quests=shiny_target,
        target_skin_quests=skin_target,
    )

    await save_player_records(interaction, records)

    return {
        "mode": "addseasonloot",
        "item": f"{item_name}{' (shiny)' if shiny else ''}",
        "season_unique_total": player_data.get_unique_item_count(),
    }


async def ingest_loot_event(payload: Dict[str, Any], notifier: Notifier | None = None) -> Dict[str, Any]:
    try:
        guild_id = int(payload.get("guild_id"))
    except (TypeError, ValueError):
        raise IngestValidationError("guild_id must be an integer.", status_code=400, error_code="invalid_guild_id")

    token = str(payload.get("link_token", "")).strip()
    if not token:
        raise IngestValidationError("link_token is required.", status_code=401, error_code="missing_link_token")

    raw_item_name = str(payload.get("item_name", "")).strip()
    item_name = _resolve_known_item_if_any(raw_item_name)
    divine = _as_bool(payload.get("divine", False))
    shiny = _as_bool(payload.get("shiny", False))

    _debug_log(f"Ingest request received guild_id={guild_id} item='{raw_item_name}' shiny={shiny} divine={divine}")

    settings = await get_realmshark_settings_by_id(guild_id)
    if not settings.get("enabled", False):
        raise IngestValidationError("RealmShark integration is disabled for this guild.", status_code=403, error_code="disabled")

    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    link_data = links.get(token)
    if not isinstance(link_data, dict):
        raise IngestValidationError("Invalid link token.", status_code=401, error_code="invalid_link_token")

    try:
        linked_user_id = int(link_data.get("user_id"))
    except (TypeError, ValueError):
        raise IngestValidationError("Linked token is misconfigured.", status_code=500, error_code="broken_link")

    event_type = str(payload.get("event_type", "")).strip().lower()
    if event_type == "bridge_settings_test":
        source = str(payload.get("source", "tomato")).strip() or "tomato"
        test_message = (
            "RealmShark bridge test succeeded. "
            f"guild_id={guild_id} user_id={linked_user_id} source={source}"
        )

        if notifier is not None:
            try:
                await notifier(guild_id, test_message)
            except Exception as e:
                _debug_log(f"Bridge test notifier error for guild={guild_id}: {e}")

        link_data["last_used_at"] = _utc_iso_now()
        links[token] = link_data
        settings["links"] = links
        await set_realmshark_settings_by_id(guild_id, settings)

        return {
            "mode": "none",
            "guild_id": guild_id,
            "user_id": linked_user_id,
            "item": "",
            "logged": False,
            "flagged_not_logged": False,
            "reason": "bridge_settings_test_ok",
            "announced": notifier is not None,
        }

    # Only items present in rotmg_loot_drops_updated.csv are logged into addloot/addseasonloot.
    # Missing UT/ST items are explicitly flagged for CSV follow-up instead of being silently dropped.
    if item_name is None:
        if _is_ut_or_st_event(payload):
            _append_missing_utst_log(guild_id, raw_item_name, payload)
            return {
                "mode": "none",
                "guild_id": guild_id,
                "user_id": linked_user_id,
                "item": raw_item_name,
                "logged": False,
                "flagged_not_logged": True,
                "reason": "ut_or_st_missing_from_rotmg_loot_drops_updated",
            }

        _debug_log(f"Skipped non-tracked non-UT/ST item '{raw_item_name}'")
        return {
            "mode": "none",
            "guild_id": guild_id,
            "user_id": linked_user_id,
            "item": raw_item_name,
            "logged": False,
            "flagged_not_logged": False,
            "reason": "item_not_in_rotmg_loot_drops_updated",
        }

    _validate_shiny_variant(item_name, shiny)

    mode = str(settings.get("mode", "addloot"))
    if mode == "addseasonloot":
        result = await _addseasonloot_for_user(guild_id, linked_user_id, item_name, shiny)
    else:
        result = await _addloot_for_user(guild_id, linked_user_id, item_name, divine, shiny)

    _debug_log(
        f"Logged item via mode={mode} guild_id={guild_id} user_id={linked_user_id} item='{item_name}'"
    )

    link_data["last_used_at"] = _utc_iso_now()
    links[token] = link_data
    settings["links"] = links
    await set_realmshark_settings_by_id(guild_id, settings)

    result["guild_id"] = guild_id
    result["user_id"] = linked_user_id
    return result
