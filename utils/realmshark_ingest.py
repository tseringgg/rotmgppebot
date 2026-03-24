from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import glob
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
from utils.realmshark_pending_store import append_pending_event, migrate_legacy_pending_map


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
_DUNGEONS_PATH = os.getenv("REALMSHARK_DUNGEONS_PATH", "dungeons")
_ITEM_IMAGE_INDEX: Dict[str, str] = {}
_ITEM_IMAGE_INDEX_READY = False
Notifier = Callable[
    [
        int,
        str,
        int | None,
        int | None,
        str | None,
        bool,
        int | None,
        bool,
    ],
    Awaitable[None],
]
_ALLOWED_RARITIES = {"common", "uncommon", "rare", "legendary", "divine"}


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _debug_log(message: str) -> None:
    if _DEBUG:
        print(f"[REALMSHARK_DEBUG] {message}")


def _info_log(message: str) -> None:
    print(f"[REALMSHARK] {message}")


def _token_preview(token: str) -> str:
    if len(token) <= 10:
        return token
    return f"{token[:6]}...{token[-4:]}"


def _strip_shiny_suffix(raw_item_name: str) -> tuple[str, bool]:
    trimmed = raw_item_name.strip()
    if trimmed.lower().endswith("(shiny)"):
        return trimmed[: -len("(shiny)")].strip(), True
    return trimmed, False


def _build_item_image_index_if_needed() -> None:
    global _ITEM_IMAGE_INDEX_READY
    if _ITEM_IMAGE_INDEX_READY:
        return

    _ITEM_IMAGE_INDEX.clear()
    pattern = os.path.join(_DUNGEONS_PATH, "**", "*.png")
    png_files = glob.glob(pattern, recursive=True)

    for png_file in png_files:
        base_name = os.path.splitext(os.path.basename(png_file))[0]
        normalized = normalize_item_name(base_name).lower()
        if not normalized:
            continue
        # Keep first occurrence to preserve deterministic routing.
        if normalized not in _ITEM_IMAGE_INDEX:
            _ITEM_IMAGE_INDEX[normalized] = png_file

    _ITEM_IMAGE_INDEX_READY = True
    _info_log(
        f"Built item image index: entries={len(_ITEM_IMAGE_INDEX)} source={_DUNGEONS_PATH}"
    )


def _resolve_item_image_path(item_name: str, shiny: bool) -> str | None:
    _build_item_image_index_if_needed()

    candidates = []
    base = item_name.strip()
    if not base:
        return None

    lower_base = base.lower()
    if shiny:
        if lower_base.endswith("(shiny)"):
            candidates.append(base)
        else:
            candidates.append(f"{base} (shiny)")
    else:
        candidates.append(base)

    for candidate in candidates:
        key = normalize_item_name(candidate).lower()
        path = _ITEM_IMAGE_INDEX.get(key)
        if path:
            return path

    return None


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


def _normalize_rarity(value: Any) -> str:
    if value is None:
        return "rare"

    raw = str(value).strip().lower()
    if not raw:
        return "rare"

    if raw in _ALLOWED_RARITIES:
        return raw

    return "rare"


def _parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _is_explicit_invalid_character_id(value: Any) -> bool:
    if value is None:
        return False
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return False
    return parsed <= 0


def _normalized_character_bindings(link_data: Dict[str, Any]) -> Dict[str, int]:
    raw = link_data.get("character_bindings", {})
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, int] = {}
    for raw_character_id, raw_ppe_id in raw.items():
        character_id = _parse_positive_int(raw_character_id)
        ppe_id = _parse_positive_int(raw_ppe_id)
        if character_id is None or ppe_id is None:
            continue
        normalized[str(character_id)] = ppe_id
    return normalized


def _normalized_seasonal_character_ids(link_data: Dict[str, Any]) -> set[str]:
    raw = link_data.get("seasonal_character_ids", [])
    values = raw if isinstance(raw, list) else []

    normalized: set[str] = set()
    for value in values:
        character_id = _parse_positive_int(value)
        if character_id is None:
            continue
        normalized.add(str(character_id))
    return normalized


def _display_rarity(rarity: str) -> str:
    normalized = _normalize_rarity(rarity)
    return normalized[:1].upper() + normalized[1:]


def _format_points(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


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
    _info_log(f"Flagged missing UT/ST item for CSV follow-up: item={item_name} guild_id={guild_id}")


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

    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records.get(key)

    if player_data is None or not player_data.is_member:
        raise IngestValidationError("Linked user is not part of the PPE contest.", status_code=403, error_code="not_member")

    ppe_id = player_data.active_ppe
    if ppe_id is None:
        raise IngestValidationError("Linked user does not have an active PPE.", status_code=409, error_code="no_active_ppe")

    return await _addloot_for_user_with_ppe(guild_id, user_id, item_name, divine, shiny, int(ppe_id))


async def _addloot_for_user_with_ppe(
    guild_id: int,
    user_id: int,
    item_name: str,
    divine: bool,
    shiny: bool,
    ppe_id: int,
) -> Dict[str, Any]:
    interaction = _SyntheticInteraction(guild=_SyntheticGuild(guild_id), user=_SyntheticUser(user_id))

    points = calc_points(item_name, divine, shiny)
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data = records.get(key)

    if player_data is None or not player_data.is_member:
        raise IngestValidationError("Linked user is not part of the PPE contest.", status_code=403, error_code="not_member")

    target_ppe = next((ppe for ppe in player_data.ppes if ppe.id == ppe_id), None)
    if target_ppe is None:
        raise IngestValidationError(
            f"Linked user does not have PPE #{ppe_id}.",
            status_code=409,
            error_code="invalid_target_ppe",
        )

    item_key, points_added, active_ppe, _quest_update = await player_manager.add_loot_and_points(
        interaction,
        user=_SyntheticUser(user_id),
        ppe_id=int(ppe_id),
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


async def _get_season_unique_total_for_user(guild_id: int, user_id: int) -> int:
    interaction = _SyntheticInteraction(guild=_SyntheticGuild(guild_id), user=_SyntheticUser(user_id))
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user_id)
    player_data: PlayerData | None = records.get(key)
    if player_data is None:
        return 0
    return player_data.get_unique_item_count()


async def _addseasonloot_with_duplicate_ok(
    guild_id: int,
    user_id: int,
    item_name: str,
    shiny: bool,
) -> Dict[str, Any]:
    try:
        result = await _addseasonloot_for_user(guild_id, user_id, item_name, shiny)
        result["already_present"] = False
        return result
    except IngestValidationError as e:
        if e.error_code != "duplicate_season_item":
            raise

        total = await _get_season_unique_total_for_user(guild_id, user_id)
        return {
            "mode": "addseasonloot",
            "item": f"{item_name}{' (shiny)' if shiny else ''}",
            "season_unique_total": total,
            "already_present": True,
            "logged": False,
            "reason": "duplicate_season_item",
        }


async def ingest_loot_event(payload: Dict[str, Any], notifier: Notifier | None = None) -> Dict[str, Any]:
    try:
        guild_id = int(payload.get("guild_id"))
    except (TypeError, ValueError):
        raise IngestValidationError("guild_id must be an integer.", status_code=400, error_code="invalid_guild_id")

    token = str(payload.get("link_token", "")).strip()
    if not token:
        raise IngestValidationError("link_token is required.", status_code=401, error_code="missing_link_token")

    event_type = str(payload.get("event_type", "")).strip().lower()
    raw_character_id = payload.get("character_id")
    character_id = _parse_positive_int(payload.get("character_id"))
    has_explicit_invalid_character_id = _is_explicit_invalid_character_id(raw_character_id)
    character_name = str(payload.get("character_name", "")).strip()
    character_class = str(payload.get("character_class", "")).strip()

    raw_item_name = str(payload.get("item_name", "")).strip()
    divine = _as_bool(payload.get("divine", False))
    shiny = _as_bool(payload.get("shiny", False))
    item_rarity = _normalize_rarity(payload.get("item_rarity", "rare"))

    normalized_item_name, suffix_shiny = _strip_shiny_suffix(raw_item_name)
    if suffix_shiny and not shiny:
        shiny = True
        _info_log(
            f"Detected '(shiny)' suffix in item_name; forcing shiny=True for guild_id={guild_id} item='{raw_item_name}'"
        )
    raw_item_name = normalized_item_name

    _debug_log(f"Ingest request received guild_id={guild_id} item='{raw_item_name}' shiny={shiny} divine={divine}")
    _info_log(
        "Payload accepted "
        f"guild_id={guild_id} token={_token_preview(token)} item='{raw_item_name}' "
        f"shiny={shiny} divine={divine} rarity={item_rarity} "
        f"event_type={event_type or 'loot'} character_id={character_id or 0} "
        f"character_class='{character_class or 'unknown'}'"
    )

    settings = await get_realmshark_settings_by_id(guild_id)
    if not settings.get("enabled", False):
        raise IngestValidationError("RealmShark integration is disabled for this guild.", status_code=403, error_code="disabled")

    links = settings.get("links", {}) if isinstance(settings.get("links"), dict) else {}
    link_data = links.get(token)
    if not isinstance(link_data, dict):
        _info_log(f"Invalid link token for guild_id={guild_id} token={_token_preview(token)}")
        raise IngestValidationError("Invalid link token.", status_code=401, error_code="invalid_link_token")

    try:
        linked_user_id = int(link_data.get("user_id"))
    except (TypeError, ValueError):
        raise IngestValidationError("Linked token is misconfigured.", status_code=500, error_code="broken_link")

    _debug_log(
        f"Token resolved guild_id={guild_id} token={_token_preview(token)} linked_user_id={linked_user_id}"
    )

    legacy_pending = link_data.get("pending_unmapped_characters", {})
    if isinstance(legacy_pending, dict) and legacy_pending:
        await migrate_legacy_pending_map(guild_id, linked_user_id, legacy_pending)
        link_data["pending_unmapped_characters"] = {}

    if character_id is not None:
        link_data["last_seen_character_id"] = character_id
        raw_meta = link_data.get("character_metadata", {})
        metadata = raw_meta if isinstance(raw_meta, dict) else {}
        key = str(character_id)
        entry = metadata.get(key, {}) if isinstance(metadata.get(key, {}), dict) else {}
        if character_name:
            entry["character_name"] = character_name
        if character_class:
            entry["character_class"] = character_class
        if entry:
            metadata[key] = entry
            link_data["character_metadata"] = metadata

    announce_channel_id: int | None = None
    announce_channel_raw = settings.get("announce_channel_id", 0)
    try:
        parsed_announce_channel_id = int(announce_channel_raw)
    except (TypeError, ValueError):
        parsed_announce_channel_id = 0
    if parsed_announce_channel_id > 0:
        announce_channel_id = parsed_announce_channel_id

    _debug_log(
        f"Announcement routing guild_id={guild_id} announce_channel_id={announce_channel_id or 0}"
    )

    if event_type == "bridge_settings_test":
        test_message = f"RealmShark is successfully bound to <@{linked_user_id}>"

        if notifier is not None:
            try:
                _debug_log(f"Dispatching bridge settings test announcement for guild_id={guild_id}")
                await notifier(
                    guild_id,
                    test_message,
                    announce_channel_id,
                    linked_user_id,
                    None,
                    True,
                    None,
                    False,
                )
                _debug_log(f"Bridge settings test announcement sent for guild_id={guild_id}")
            except Exception as e:
                _info_log(f"Bridge test notifier error for guild_id={guild_id}: {e}")
                _debug_log(f"Bridge test notifier error for guild={guild_id}: {e}")
        else:
            _debug_log(f"Bridge settings test received for guild_id={guild_id} but notifier is not configured")

        link_data["last_used_at"] = _utc_iso_now()
        links[token] = link_data
        settings["links"] = links
        await set_realmshark_settings_by_id(guild_id, settings)
        _debug_log(f"Updated last_used_at for bridge settings test token in guild_id={guild_id}")

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

    item_name = _resolve_known_item_if_any(raw_item_name)

    # Only items present in rotmg_loot_drops_updated.csv are logged into addloot/addseasonloot.
    # Missing UT/ST items are explicitly flagged for CSV follow-up instead of being silently dropped.
    if item_name is None:
        if _is_ut_or_st_event(payload):
            _info_log(
                f"Item not in tracked CSV but identified as UT/ST: guild_id={guild_id} item='{raw_item_name}'"
            )
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
        _debug_log(
            f"Skipped non-tracked non-UT/ST item: guild_id={guild_id} item='{raw_item_name}'"
        )
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
    _debug_log(
        f"Resolved tracked item for logging: guild_id={guild_id} item='{item_name}' shiny={shiny}"
    )

    mode = str(settings.get("mode", "addloot"))
    routing_reason = "legacy_mode"
    used_character_binding = False
    mapped_ppe_id: int | None = None
    ingest_warning: str | None = None

    if character_id is not None:
        key = str(character_id)
        bindings = _normalized_character_bindings(link_data)
        seasonal_ids = _normalized_seasonal_character_ids(link_data)
        bound_ppe_id = _parse_positive_int(bindings.get(key))

        if key in seasonal_ids:
            mode = "addseasonloot"
            routing_reason = "mapped_seasonal_character"
            _debug_log(
                f"Character_id={character_id} explicitly mapped to seasonal. "
                f"Routing to addseasonloot guild_id={guild_id} user_id={linked_user_id}"
            )
            result = await _addseasonloot_with_duplicate_ok(guild_id, linked_user_id, item_name, shiny)
        elif bound_ppe_id is not None:
            try:
                mode = "addloot"
                routing_reason = "mapped_character"
                used_character_binding = True
                mapped_ppe_id = bound_ppe_id
                _debug_log(
                    f"Routing via mapped character_id={character_id} ppe_id={bound_ppe_id} "
                    f"guild_id={guild_id} user_id={linked_user_id}"
                )
                result = await _addloot_for_user_with_ppe(
                    guild_id,
                    linked_user_id,
                    item_name,
                    divine,
                    shiny,
                    bound_ppe_id,
                )
            except IngestValidationError as e:
                _info_log(
                    f"Mapped PPE routing failed for character_id={character_id} ppe_id={bound_ppe_id} "
                    f"guild_id={guild_id} user_id={linked_user_id}: {e.message}. Falling back to addseasonloot."
                )
                mode = "addseasonloot"
                routing_reason = "mapped_character_fallback_to_season"
                result = await _addseasonloot_with_duplicate_ok(guild_id, linked_user_id, item_name, shiny)
        else:
            mode = "addseasonloot"
            routing_reason = "unmapped_character"
            _debug_log(
                f"Unmapped character_id={character_id}; routing to addseasonloot "
                f"guild_id={guild_id} user_id={linked_user_id}"
            )
            result = await _addseasonloot_with_duplicate_ok(guild_id, linked_user_id, item_name, shiny)

            is_first_unmapped = await append_pending_event(
                guild_id,
                linked_user_id,
                character_id=character_id,
                item_name=item_name,
                item_rarity=_normalize_rarity(item_rarity),
                shiny=shiny,
                divine=divine,
                character_name=character_name,
                character_class=character_class,
            )

            if is_first_unmapped and notifier is not None:
                try:
                    prompt = (
                        f"<@{linked_user_id}> New character detected (`{character_id}`). "
                        "Loot is currently tracked as seasonal. "
                        "Use `/realmsharkconfigure` to map this character to a PPE or keep it seasonal."
                    )
                    await notifier(
                        guild_id,
                        prompt,
                        announce_channel_id,
                        linked_user_id,
                        None,
                        True,
                        None,
                        False,
                    )
                except Exception as e:
                    _info_log(
                        f"Failed to send unmapped-character prompt guild_id={guild_id} "
                        f"user_id={linked_user_id} character_id={character_id}: {e}"
                    )
    else:
        if has_explicit_invalid_character_id:
            mode = "addseasonloot"
            routing_reason = "invalid_character_id"
            ingest_warning = (
                "RealmShark sent an invalid character_id (0 or negative). "
                "Loot was logged to seasonal to prevent misrouting. "
                "Please update your sniffer and/or reach out to the bot devs to investigate this issue."
            )
            _info_log(
                f"Invalid character_id received; forcing addseasonloot guild_id={guild_id} "
                f"user_id={linked_user_id} raw_character_id={raw_character_id!r}"
            )
            result = await _addseasonloot_with_duplicate_ok(guild_id, linked_user_id, item_name, shiny)
        elif mode == "addseasonloot":
            _debug_log(
                f"Dispatching loot event using legacy mode={mode} guild_id={guild_id} user_id={linked_user_id}"
            )
            result = await _addseasonloot_with_duplicate_ok(guild_id, linked_user_id, item_name, shiny)
        else:
            _debug_log(
                f"Dispatching loot event using legacy mode={mode} guild_id={guild_id} user_id={linked_user_id}"
            )
            result = await _addloot_for_user(guild_id, linked_user_id, item_name, divine, shiny)

    _debug_log(
        f"Logged item via mode={mode} guild_id={guild_id} user_id={linked_user_id} item='{item_name}'"
    )

    link_data["last_used_at"] = _utc_iso_now()
    links[token] = link_data
    settings["links"] = links
    await set_realmshark_settings_by_id(guild_id, settings)
    _debug_log(
        f"Updated last_used_at after loot logging: guild_id={guild_id} user_id={linked_user_id} item='{item_name}'"
    )

    result["guild_id"] = guild_id
    result["user_id"] = linked_user_id
    result["item_rarity"] = item_rarity
    result["character_id"] = character_id or 0
    result["routing_reason"] = routing_reason
    result["used_character_binding"] = used_character_binding
    result["mapped_ppe_id"] = mapped_ppe_id
    if ingest_warning is not None:
        result["warning"] = ingest_warning

    if notifier is not None:
        image_path = _resolve_item_image_path(item_name, shiny)
        image_missing = image_path is None
        if image_path:
            _debug_log(
                f"Resolved loot image for announcement: guild_id={guild_id} item='{item_name}' shiny={shiny} path={image_path}"
            )
        else:
            _debug_log(
                f"No loot image found for announcement: guild_id={guild_id} item='{item_name}' shiny={shiny}"
            )

        announced_item = str(result.get("item", item_name))
        if shiny and "(shiny)" not in announced_item.lower():
            announced_item = f"{announced_item} (shiny)"

        display_rarity = _display_rarity(item_rarity)

        destination = "seasonal loot"
        if mode == "addloot" and mapped_ppe_id is not None:
            destination = f"PPE #{mapped_ppe_id}"

        announcement = (
            f"{{player}} got {display_rarity} {announced_item}. "
            f"It was logged to {destination}."
        )

        if mode == "addloot" and mapped_ppe_id is not None:
            points_added = float(result.get("points_added", 0) or 0)
            new_points = float(result.get("total_points", 0) or 0)
            old_points = new_points - points_added
            announcement += (
                f" Points: {_format_points(old_points)} -> {_format_points(new_points)}"
            )

        if bool(result.get("already_present", False)):
            announcement = (
                f"{{player}} got {display_rarity} {announced_item}. "
                f"It was already logged to {destination}."
            )
            if routing_reason == "unmapped_character":
                announcement += (
                    " | new character is still unmapped, use /realmsharkconfigure to choose PPE vs seasonal"
                )

        if ingest_warning is not None:
            announcement += (
                " | warning: invalid character_id from sniffer. "
                "Please update sniffer and/or contact bot devs to investigate."
            )

        if image_missing:
            announcement += " | image missing"

        try:
            _debug_log(
                f"Dispatching loot announcement guild_id={guild_id} user_id={linked_user_id} item={result.get('item', item_name)}"
            )
            await notifier(
                guild_id,
                announcement,
                announce_channel_id,
                linked_user_id,
                image_path,
                False,
                mapped_ppe_id,
                mode == "addloot" and mapped_ppe_id is not None,
            )
            _debug_log(
                f"Loot announcement sent guild_id={guild_id} user_id={linked_user_id} item={result.get('item', item_name)}"
            )
        except Exception as e:
            _info_log(f"Loot announcement failed guild_id={guild_id} user_id={linked_user_id}: {e}")
            _debug_log(f"Loot announcement failed guild_id={guild_id} user_id={linked_user_id}: {e}")

    _info_log(
        "Completed ingest "
        f"guild_id={guild_id} user_id={linked_user_id} reason={result.get('mode', '')} item={result.get('item', '')}"
    )
    return result
