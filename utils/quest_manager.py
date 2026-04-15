"""Utilities for quest manager."""

import csv
import random
from typing import Any, Dict, List, Tuple

from dataclass import PlayerData
from utils.calc_points import load_loot_points, normalize_item_name
from utils.season_loot_history import season_unique_items

_LOOT_CSV = "rotmg_loot_drops_updated.csv"
_REGULAR_BY_NORM: Dict[str, str] = {}
_SHINY_BY_NORM: Dict[str, str] = {}
_SKIN_BY_NORM: Dict[str, str] = {}
_LIMITED_BY_NORM: Dict[str, str] = {}
_POOLS_LOADED = False

DEFAULT_REGULAR_QUEST_TARGET = 8
DEFAULT_SHINY_QUEST_TARGET = 3
DEFAULT_SKIN_QUEST_TARGET = 1

RESETTABLE_QUEST_SECTIONS = {
    "current_items",
    "current_shinies",
    "current_skins",
    "completed_items",
    "completed_shinies",
    "completed_skins",
}


def _is_shiny_name(item_name: str) -> bool:
    return normalize_item_name(item_name).lower().endswith(" (shiny)")


def _load_quest_pools() -> None:
    global _POOLS_LOADED
    if _POOLS_LOADED:
        return

    with open(_LOOT_CSV, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            item_name = normalize_item_name(row.get("Item Name", ""))
            loot_type = normalize_item_name(row.get("Loot Type", "")).lower()
            if not item_name:
                continue

            # Keep shiny entries out of regular/skin pools so categories stay strict.
            if _is_shiny_name(item_name):
                continue

            normalized = normalize_item_name(item_name).lower()
            if loot_type == "skin":
                _SKIN_BY_NORM.setdefault(normalized, item_name)
            elif loot_type == "limited":
                _LIMITED_BY_NORM.setdefault(normalized, item_name)
            elif loot_type not in {"item", "limited", "skin"}:
                _REGULAR_BY_NORM.setdefault(normalized, item_name)

    # Build shiny-capable pool from available shiny variants in points table.
    loot_points = load_loot_points()
    for point_key in loot_points:
        normalized_key = normalize_item_name(point_key).lower()
        shiny_suffix = " (shiny)"
        if not normalized_key.endswith(shiny_suffix):
            continue

        base_norm = normalized_key[: -len(shiny_suffix)].strip()
        if base_norm in _REGULAR_BY_NORM:
            _SHINY_BY_NORM.setdefault(base_norm, _REGULAR_BY_NORM[base_norm])

    _POOLS_LOADED = True


def _normalized_set(items: List[str]) -> set[str]:
    return {normalize_item_name(item).lower() for item in items}


def _contains_name(items: List[str], item_name: str) -> bool:
    target = normalize_item_name(item_name).lower()
    return any(normalize_item_name(item).lower() == target for item in items)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        normalized = normalize_item_name(item)
        lowered = normalized.lower()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        result.append(normalized)
    return result


def _is_global_mode_enabled(global_quests: dict | None) -> bool:
    return bool(global_quests and bool(global_quests.get("enabled")))


def _is_team_mode_enabled(team_quests: dict | None) -> bool:
    if not team_quests:
        return False
    if not bool(team_quests.get("enabled")):
        return False
    return bool(team_quests.get("team_key"))


def _blank_team_state() -> dict[str, list[str]]:
    return {
        "current_items": [],
        "current_shinies": [],
        "current_skins": [],
        "completed_items": [],
        "completed_shinies": [],
        "completed_skins": [],
    }


def _team_state_lists(state: dict[str, Any], key: str) -> list[str]:
    value = state.get(key)
    if not isinstance(value, list):
        value = []
    cleaned = _dedupe_preserve_order([str(item) for item in value if isinstance(item, str) and str(item).strip()])
    state[key] = cleaned
    return cleaned


def _sanitize_team_state_buckets(state: dict[str, Any]) -> bool:
    changed = False

    current_items = _team_state_lists(state, "current_items")
    current_shinies = _team_state_lists(state, "current_shinies")
    completed_items = _team_state_lists(state, "completed_items")
    completed_shinies = _team_state_lists(state, "completed_shinies")

    moved_current = [quest for quest in current_items if _is_shiny_name(quest)]
    if moved_current:
        state["current_items"] = [quest for quest in current_items if not _is_shiny_name(quest)]
        merged = list(current_shinies)
        for quest in moved_current:
            if not _contains_name(merged, quest):
                merged.append(quest)
        state["current_shinies"] = merged
        changed = True

    moved_completed = [quest for quest in completed_items if _is_shiny_name(quest)]
    if moved_completed:
        state["completed_items"] = [quest for quest in completed_items if not _is_shiny_name(quest)]
        merged = list(completed_shinies)
        for quest in moved_completed:
            if not _contains_name(merged, quest):
                merged.append(quest)
        state["completed_shinies"] = merged
        changed = True

    _team_state_lists(state, "current_skins")
    _team_state_lists(state, "completed_skins")
    return changed


def _team_owned_norms(member_records: list[PlayerData]) -> tuple[set[str], set[str]]:
    owned_regular: set[str] = set()
    owned_shiny_targets: set[str] = set()
    for member_data in member_records:
        for item_name, shiny in season_unique_items(member_data):
            if not shiny:
                owned_regular.add(normalize_item_name(item_name).lower())
            if shiny:
                owned_shiny_targets.add(_quest_target_norm(item_name, shiny=True))
    return owned_regular, owned_shiny_targets


def _fill_missing_team_quests(
    state: dict[str, Any],
    *,
    owned_regular_norms: set[str],
    owned_shiny_target_norms: set[str],
    target_item_quests: int,
    target_shiny_quests: int,
    target_skin_quests: int,
) -> tuple[list[str], list[str], list[str]]:
    _load_quest_pools()

    current_items = _team_state_lists(state, "current_items")
    current_shinies = _team_state_lists(state, "current_shinies")
    current_skins = _team_state_lists(state, "current_skins")
    completed_items = _team_state_lists(state, "completed_items")
    completed_shinies = _team_state_lists(state, "completed_shinies")
    completed_skins = _team_state_lists(state, "completed_skins")

    added_items: list[str] = []
    added_shinies: list[str] = []
    added_skins: list[str] = []

    blocked_regular = _normalized_set(current_items + completed_items)
    regular_slots = max(0, target_item_quests - len(current_items))
    if regular_slots > 0:
        preferred_regular = _pick_random_from_pool(
            _REGULAR_BY_NORM,
            blocked_regular | owned_regular_norms,
            regular_slots,
        )
        for item in preferred_regular:
            if not _contains_name(current_items, item):
                current_items.append(item)
                added_items.append(item)

        remaining = max(0, regular_slots - len(preferred_regular))
        if remaining > 0:
            fallback_pool = dict(_REGULAR_BY_NORM)
            fallback_pool.update(_LIMITED_BY_NORM)
            fallback_regular = _pick_random_from_pool(fallback_pool, _normalized_set(current_items + completed_items), remaining)
            for item in fallback_regular:
                if not _contains_name(current_items, item):
                    current_items.append(item)
                    added_items.append(item)

    blocked_shiny = _normalized_set(current_shinies + completed_shinies)
    shiny_slots = max(0, target_shiny_quests - len(current_shinies))
    if shiny_slots > 0:
        preferred_shiny = _pick_random_shiny_from_pool(
            _SHINY_BY_NORM,
            blocked_shiny | owned_shiny_target_norms,
            shiny_slots,
        )
        for shiny_item in preferred_shiny:
            if not _contains_name(current_shinies, shiny_item):
                current_shinies.append(shiny_item)
                added_shinies.append(shiny_item)

        remaining = max(0, shiny_slots - len(preferred_shiny))
        if remaining > 0:
            fallback_shiny = _pick_random_shiny_from_pool(_SHINY_BY_NORM, _normalized_set(current_shinies + completed_shinies), remaining)
            for shiny_item in fallback_shiny:
                if not _contains_name(current_shinies, shiny_item):
                    current_shinies.append(shiny_item)
                    added_shinies.append(shiny_item)

    blocked_skins = _normalized_set(current_skins + completed_skins)
    skin_slots = max(0, target_skin_quests - len(current_skins))
    if skin_slots > 0:
        preferred_skins = _pick_random_from_pool(_SKIN_BY_NORM, blocked_skins | owned_regular_norms, skin_slots)
        for skin in preferred_skins:
            if not _contains_name(current_skins, skin):
                current_skins.append(skin)
                added_skins.append(skin)

        remaining = max(0, skin_slots - len(preferred_skins))
        if remaining > 0:
            fallback_skins = _pick_random_from_pool(_SKIN_BY_NORM, _normalized_set(current_skins + completed_skins), remaining)
            for skin in fallback_skins:
                if not _contains_name(current_skins, skin):
                    current_skins.append(skin)
                    added_skins.append(skin)

    state["current_items"] = current_items
    state["current_shinies"] = current_shinies
    state["current_skins"] = current_skins
    return added_items, added_shinies, added_skins


def _project_team_state_to_member(member_data: PlayerData, state: dict[str, Any]) -> bool:
    quests = member_data.quests
    changed = False

    target_items = list(state.get("current_items", []))
    target_shinies = list(state.get("current_shinies", []))
    target_skins = list(state.get("current_skins", []))
    target_completed_items = list(state.get("completed_items", []))
    target_completed_shinies = list(state.get("completed_shinies", []))
    target_completed_skins = list(state.get("completed_skins", []))

    if quests.current_items != target_items:
        quests.current_items = target_items
        changed = True
    if quests.current_shinies != target_shinies:
        quests.current_shinies = target_shinies
        changed = True
    if quests.current_skins != target_skins:
        quests.current_skins = target_skins
        changed = True
    if quests.completed_items != target_completed_items:
        quests.completed_items = target_completed_items
        changed = True
    if quests.completed_shinies != target_completed_shinies:
        quests.completed_shinies = target_completed_shinies
        changed = True
    if quests.completed_skins != target_completed_skins:
        quests.completed_skins = target_completed_skins
        changed = True

    return changed


def _apply_team_quests_mode(
    player_data: PlayerData,
    team_quests: dict | None,
    *,
    target_item_quests: int,
    target_shiny_quests: int,
    target_skin_quests: int,
) -> bool:
    if not _is_team_mode_enabled(team_quests):
        return False

    state_map = team_quests.get("team_state_map")
    team_key = str(team_quests.get("team_key") or "").strip().lower()
    member_records = team_quests.get("member_records") or []
    if not isinstance(state_map, dict) or not team_key:
        return False

    state = state_map.get(team_key)
    if not isinstance(state, dict):
        state = _blank_team_state()
        state_map[team_key] = state

    changed = _sanitize_team_state_buckets(state)
    owned_regular_norms, owned_shiny_target_norms = _team_owned_norms(member_records or [player_data])

    current_items = _team_state_lists(state, "current_items")
    current_shinies = _team_state_lists(state, "current_shinies")
    current_skins = _team_state_lists(state, "current_skins")
    completed_items = _team_state_lists(state, "completed_items")
    completed_shinies = _team_state_lists(state, "completed_shinies")
    completed_skins = _team_state_lists(state, "completed_skins")

    if len(current_items) > target_item_quests:
        state["current_items"] = current_items[:target_item_quests]
        current_items = state["current_items"]
        changed = True
    if len(current_shinies) > target_shiny_quests:
        state["current_shinies"] = current_shinies[:target_shiny_quests]
        current_shinies = state["current_shinies"]
        changed = True
    if len(current_skins) > target_skin_quests:
        state["current_skins"] = current_skins[:target_skin_quests]
        current_skins = state["current_skins"]
        changed = True

    keep_regular: list[str] = []
    for quest in current_items:
        if normalize_item_name(quest).lower() in owned_regular_norms:
            if not _contains_name(completed_items, quest):
                completed_items.append(quest)
            changed = True
        else:
            keep_regular.append(quest)
    state["current_items"] = keep_regular

    keep_shiny: list[str] = []
    for quest in current_shinies:
        if normalize_item_name(quest).lower() in owned_shiny_target_norms:
            if not _contains_name(completed_shinies, quest):
                completed_shinies.append(quest)
            changed = True
        else:
            keep_shiny.append(quest)
    state["current_shinies"] = keep_shiny

    keep_skins: list[str] = []
    for quest in current_skins:
        if normalize_item_name(quest).lower() in owned_regular_norms:
            if not _contains_name(completed_skins, quest):
                completed_skins.append(quest)
            changed = True
        else:
            keep_skins.append(quest)
    state["current_skins"] = keep_skins

    added_items, added_shinies, added_skins = _fill_missing_team_quests(
        state,
        owned_regular_norms=owned_regular_norms,
        owned_shiny_target_norms=owned_shiny_target_norms,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )
    if added_items or added_shinies or added_skins:
        changed = True

    projected_members = member_records or [player_data]
    for member_data in projected_members:
        if _project_team_state_to_member(member_data, state):
            changed = True

    if player_data not in projected_members and _project_team_state_to_member(player_data, state):
        changed = True

    return changed


def _apply_global_quests_mode(player_data: PlayerData, global_quests: dict | None) -> bool:
    if not _is_global_mode_enabled(global_quests):
        return False

    quests = player_data.quests
    regular_pool = _dedupe_preserve_order(list(global_quests.get("regular", [])))
    shiny_pool = _dedupe_preserve_order(list(global_quests.get("shiny", [])))
    skin_pool = _dedupe_preserve_order(list(global_quests.get("skin", [])))

    changed = False

    target_regular = [item for item in regular_pool if not _contains_name(quests.completed_items, item)]
    target_shiny = [item for item in shiny_pool if not _contains_name(quests.completed_shinies, item)]
    target_skin = [item for item in skin_pool if not _contains_name(quests.completed_skins, item)]

    if quests.current_items != target_regular:
        quests.current_items = target_regular
        changed = True
    if quests.current_shinies != target_shiny:
        quests.current_shinies = target_shiny
        changed = True
    if quests.current_skins != target_skin:
        quests.current_skins = target_skin
        changed = True

    return changed


def _quest_target_name(item_name: str, shiny: bool = False) -> str:
    normalized = normalize_item_name(item_name)
    if shiny and not normalized.lower().endswith(" (shiny)"):
        return f"{normalized} (shiny)"
    return normalized


def _quest_target_norm(item_name: str, shiny: bool = False) -> str:
    return normalize_item_name(_quest_target_name(item_name, shiny)).lower()


def _owned_regular_norms(player_data: PlayerData) -> set[str]:
    owned = set()
    for item_name, shiny in season_unique_items(player_data):
        if not shiny:
            owned.add(normalize_item_name(item_name).lower())
    return owned


def _owned_shiny_target_norms(player_data: PlayerData) -> set[str]:
    owned = set()
    for item_name, shiny in season_unique_items(player_data):
        if shiny:
            owned.add(_quest_target_norm(item_name, shiny=True))
    return owned


def _pick_random_from_pool(pool: Dict[str, str], blocked: set[str], count: int) -> List[str]:
    candidates = [display for norm, display in pool.items() if norm not in blocked]
    if not candidates or count <= 0:
        return []
    if len(candidates) <= count:
        random.shuffle(candidates)
        return candidates
    return random.sample(candidates, count)


def _pick_random_shiny_from_pool(pool: Dict[str, str], blocked_targets: set[str], count: int) -> List[str]:
    candidates = [
        _quest_target_name(display, shiny=True)
        for _norm, display in pool.items()
        if _quest_target_norm(display, shiny=True) not in blocked_targets
    ]
    if not candidates or count <= 0:
        return []
    if len(candidates) <= count:
        random.shuffle(candidates)
        return candidates
    return random.sample(candidates, count)


def _sanitize_quest_buckets(player_data: PlayerData) -> bool:
    """Move any shiny-labeled entries out of regular buckets into shiny buckets."""
    quests = player_data.quests
    changed = False

    moved_current = [quest for quest in quests.current_items if _is_shiny_name(quest)]
    if moved_current:
        quests.current_items = [quest for quest in quests.current_items if not _is_shiny_name(quest)]
        for quest in moved_current:
            if not _contains_name(quests.current_shinies, quest):
                quests.current_shinies.append(quest)
        changed = True

    moved_completed = [quest for quest in quests.completed_items if _is_shiny_name(quest)]
    if moved_completed:
        quests.completed_items = [quest for quest in quests.completed_items if not _is_shiny_name(quest)]
        for quest in moved_completed:
            if not _contains_name(quests.completed_shinies, quest):
                quests.completed_shinies.append(quest)
        changed = True

    return changed


def _fill_missing_quests(
    player_data: PlayerData,
    target_item_quests: int = DEFAULT_REGULAR_QUEST_TARGET,
    target_shiny_quests: int = DEFAULT_SHINY_QUEST_TARGET,
    target_skin_quests: int = DEFAULT_SKIN_QUEST_TARGET,
) -> Tuple[List[str], List[str], List[str]]:
    _load_quest_pools()
    quests = player_data.quests

    newly_added_items: List[str] = []
    newly_added_shinies: List[str] = []
    newly_added_skins: List[str] = []

    owned_regular_norms = _owned_regular_norms(player_data)
    owned_shiny_target_norms = _owned_shiny_target_norms(player_data)

    current_and_completed_items = _normalized_set(quests.current_items + quests.completed_items)
    blocked_item_norms = owned_regular_norms | current_and_completed_items

    item_slots = max(0, target_item_quests - len(quests.current_items))
    item_replacements = _pick_random_from_pool(_REGULAR_BY_NORM, blocked_item_norms, item_slots)
    for item in item_replacements:
        if not _contains_name(quests.current_items, item):
            quests.current_items.append(item)
            newly_added_items.append(item)

    current_and_completed_shinies = _normalized_set(quests.current_shinies + quests.completed_shinies)
    blocked_shiny_targets = owned_shiny_target_norms | current_and_completed_shinies

    shiny_slots = max(0, target_shiny_quests - len(quests.current_shinies))
    shiny_replacements = _pick_random_shiny_from_pool(_SHINY_BY_NORM, blocked_shiny_targets, shiny_slots)
    for shiny_item in shiny_replacements:
        if not _contains_name(quests.current_shinies, shiny_item):
            quests.current_shinies.append(shiny_item)
            newly_added_shinies.append(shiny_item)

    current_and_completed_skins = _normalized_set(quests.current_skins + quests.completed_skins)
    blocked_skin_norms = owned_regular_norms | current_and_completed_skins

    skin_slots = max(0, target_skin_quests - len(quests.current_skins))
    skin_replacements = _pick_random_from_pool(_SKIN_BY_NORM, blocked_skin_norms, skin_slots)
    for skin in skin_replacements:
        if not _contains_name(quests.current_skins, skin):
            quests.current_skins.append(skin)
            newly_added_skins.append(skin)

    return newly_added_items, newly_added_shinies, newly_added_skins


def initialize_quests_if_needed(
    player_data: PlayerData,
    target_item_quests: int = DEFAULT_REGULAR_QUEST_TARGET,
    target_shiny_quests: int = DEFAULT_SHINY_QUEST_TARGET,
    target_skin_quests: int = DEFAULT_SKIN_QUEST_TARGET,
) -> bool:
    replacement_items, replacement_shinies, replacement_skins = _fill_missing_quests(
        player_data,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )
    return bool(replacement_items or replacement_shinies or replacement_skins)


def refresh_player_quests(
    player_data: PlayerData,
    target_item_quests: int = DEFAULT_REGULAR_QUEST_TARGET,
    target_shiny_quests: int = DEFAULT_SHINY_QUEST_TARGET,
    target_skin_quests: int = DEFAULT_SKIN_QUEST_TARGET,
    global_quests: dict | None = None,
    team_quests: dict | None = None,
) -> bool:
    sanitized = _sanitize_quest_buckets(player_data)

    if _is_global_mode_enabled(global_quests):
        return bool(sanitized or _apply_global_quests_mode(player_data, global_quests))

    if _is_team_mode_enabled(team_quests):
        return bool(
            sanitized
            or _apply_team_quests_mode(
                player_data,
                team_quests,
                target_item_quests=target_item_quests,
                target_shiny_quests=target_shiny_quests,
                target_skin_quests=target_skin_quests,
            )
        )

    initialized = initialize_quests_if_needed(
        player_data,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )
    changed = bool(sanitized or initialized)
    quests = player_data.quests

    # Enforce configured target caps before completion checks/refills.
    if len(quests.current_items) > target_item_quests:
        quests.current_items = quests.current_items[:target_item_quests]
        changed = True
    if len(quests.current_shinies) > target_shiny_quests:
        quests.current_shinies = quests.current_shinies[:target_shiny_quests]
        changed = True
    if len(quests.current_skins) > target_skin_quests:
        quests.current_skins = quests.current_skins[:target_skin_quests]
        changed = True

    owned_regular_norms = _owned_regular_norms(player_data)
    owned_shiny_targets = _owned_shiny_target_norms(player_data)

    remaining_item_quests = []
    for quest in quests.current_items:
        if normalize_item_name(quest).lower() in owned_regular_norms:
            if not _contains_name(quests.completed_items, quest):
                quests.completed_items.append(quest)
            changed = True
        else:
            remaining_item_quests.append(quest)
    quests.current_items = remaining_item_quests

    remaining_shiny_quests = []
    for quest in quests.current_shinies:
        if normalize_item_name(quest).lower() in owned_shiny_targets:
            if not _contains_name(quests.completed_shinies, quest):
                quests.completed_shinies.append(quest)
            changed = True
        else:
            remaining_shiny_quests.append(quest)
    quests.current_shinies = remaining_shiny_quests

    remaining_skin_quests = []
    for quest in quests.current_skins:
        if normalize_item_name(quest).lower() in owned_regular_norms:
            if not _contains_name(quests.completed_skins, quest):
                quests.completed_skins.append(quest)
            changed = True
        else:
            remaining_skin_quests.append(quest)
    quests.current_skins = remaining_skin_quests

    replacement_items, replacement_shinies, replacement_skins = _fill_missing_quests(
        player_data,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )
    return bool(changed or replacement_items or replacement_shinies or replacement_skins)


def update_quests_for_item(
    player_data: PlayerData,
    item_name: str,
    shiny: bool = False,
    target_item_quests: int = DEFAULT_REGULAR_QUEST_TARGET,
    target_shiny_quests: int = DEFAULT_SHINY_QUEST_TARGET,
    target_skin_quests: int = DEFAULT_SKIN_QUEST_TARGET,
    global_quests: dict | None = None,
    team_quests: dict | None = None,
) -> dict:
    sanitized = _sanitize_quest_buckets(player_data)
    if _is_global_mode_enabled(global_quests):
        initialized = _apply_global_quests_mode(player_data, global_quests)
    elif _is_team_mode_enabled(team_quests):
        state_map = team_quests.get("team_state_map") if isinstance(team_quests, dict) else None
        team_key = str((team_quests or {}).get("team_key") or "").strip().lower()
        state_before = {}
        if isinstance(state_map, dict) and team_key in state_map and isinstance(state_map[team_key], dict):
            existing = state_map[team_key]
            state_before = {
                "current_items": list(existing.get("current_items", [])),
                "current_shinies": list(existing.get("current_shinies", [])),
                "current_skins": list(existing.get("current_skins", [])),
                "completed_items": list(existing.get("completed_items", [])),
                "completed_shinies": list(existing.get("completed_shinies", [])),
                "completed_skins": list(existing.get("completed_skins", [])),
            }

        initialized = _apply_team_quests_mode(
            player_data,
            team_quests,
            target_item_quests=target_item_quests,
            target_shiny_quests=target_shiny_quests,
            target_skin_quests=target_skin_quests,
        )

        if isinstance(state_map, dict) and team_key in state_map and isinstance(state_map[team_key], dict):
            existing = state_map[team_key]
            completed_items = [
                quest for quest in existing.get("completed_items", [])
                if not _contains_name(state_before.get("completed_items", []), quest)
            ]
            completed_shinies = [
                quest for quest in existing.get("completed_shinies", [])
                if not _contains_name(state_before.get("completed_shinies", []), quest)
            ]
            completed_skins = [
                quest for quest in existing.get("completed_skins", [])
                if not _contains_name(state_before.get("completed_skins", []), quest)
            ]
            replacement_items = [
                quest for quest in existing.get("current_items", [])
                if not _contains_name(state_before.get("current_items", []), quest)
            ]
            replacement_shinies = [
                quest for quest in existing.get("current_shinies", [])
                if not _contains_name(state_before.get("current_shinies", []), quest)
            ]
            replacement_skins = [
                quest for quest in existing.get("current_skins", [])
                if not _contains_name(state_before.get("current_skins", []), quest)
            ]
        else:
            completed_items = []
            completed_shinies = []
            completed_skins = []
            replacement_items = []
            replacement_shinies = []
            replacement_skins = []

        return {
            "initialized": initialized,
            "completed_items": completed_items,
            "completed_shinies": completed_shinies,
            "completed_skins": completed_skins,
            "replacement_items": replacement_items,
            "replacement_shinies": replacement_shinies,
            "replacement_skins": replacement_skins,
            "team_state_changed": bool(initialized),
            "changed": bool(
                sanitized
                or initialized
                or completed_items
                or completed_shinies
                or completed_skins
                or replacement_items
                or replacement_shinies
                or replacement_skins
            ),
        }
    else:
        initialized = initialize_quests_if_needed(
            player_data,
            target_item_quests=target_item_quests,
            target_shiny_quests=target_shiny_quests,
            target_skin_quests=target_skin_quests,
        )

    normalized_regular = normalize_item_name(item_name).lower()
    normalized_shiny = _quest_target_norm(item_name, shiny=True)

    quests = player_data.quests

    completed_items: List[str] = []
    completed_shinies: List[str] = []
    completed_skins: List[str] = []

    remaining_item_quests = []
    for quest in quests.current_items:
        if not shiny and normalize_item_name(quest).lower() == normalized_regular:
            completed_items.append(quest)
            if not _contains_name(quests.completed_items, quest):
                quests.completed_items.append(quest)
        else:
            remaining_item_quests.append(quest)
    quests.current_items = remaining_item_quests

    remaining_shiny_quests = []
    for quest in quests.current_shinies:
        if shiny and normalize_item_name(quest).lower() == normalized_shiny:
            completed_shinies.append(quest)
            if not _contains_name(quests.completed_shinies, quest):
                quests.completed_shinies.append(quest)
        else:
            remaining_shiny_quests.append(quest)
    quests.current_shinies = remaining_shiny_quests

    remaining_skin_quests = []
    for quest in quests.current_skins:
        if not shiny and normalize_item_name(quest).lower() == normalized_regular:
            completed_skins.append(quest)
            if not _contains_name(quests.completed_skins, quest):
                quests.completed_skins.append(quest)
        else:
            remaining_skin_quests.append(quest)
    quests.current_skins = remaining_skin_quests

    replacement_items: List[str] = []
    replacement_shinies: List[str] = []
    replacement_skins: List[str] = []
    if completed_items or completed_shinies or completed_skins or initialized:
        if _is_global_mode_enabled(global_quests):
            _apply_global_quests_mode(player_data, global_quests)
        else:
            replacement_items, replacement_shinies, replacement_skins = _fill_missing_quests(
                player_data,
                target_item_quests=target_item_quests,
                target_shiny_quests=target_shiny_quests,
                target_skin_quests=target_skin_quests,
            )

    return {
        "initialized": initialized,
        "completed_items": completed_items,
        "completed_shinies": completed_shinies,
        "completed_skins": completed_skins,
        "replacement_items": replacement_items,
        "replacement_shinies": replacement_shinies,
        "replacement_skins": replacement_skins,
        "team_state_changed": False,
        "changed": bool(
            sanitized
            or initialized
            or completed_items
            or completed_shinies
            or completed_skins
            or replacement_items
            or replacement_shinies
            or replacement_skins
        ),
    }


def remove_item_from_completed_quests(player_data: PlayerData, item_name: str, shiny: bool = False) -> dict:
    """Remove matching item from completed quest lists after season-loot removal."""
    quests = player_data.quests
    normalized_regular = normalize_item_name(item_name).lower()
    normalized_shiny = _quest_target_norm(item_name, shiny=True)

    removed_completed_items = [
        quest for quest in quests.completed_items
        if not shiny and normalize_item_name(quest).lower() == normalized_regular
    ]
    removed_completed_skins = [
        quest for quest in quests.completed_skins
        if not shiny and normalize_item_name(quest).lower() == normalized_regular
    ]
    removed_completed_shinies = [
        quest for quest in quests.completed_shinies
        if shiny and normalize_item_name(quest).lower() == normalized_shiny
    ]

    if removed_completed_items:
        quests.completed_items = [
            quest for quest in quests.completed_items
            if normalize_item_name(quest).lower() != normalized_regular
        ]
    if removed_completed_skins:
        quests.completed_skins = [
            quest for quest in quests.completed_skins
            if normalize_item_name(quest).lower() != normalized_regular
        ]
    if removed_completed_shinies:
        quests.completed_shinies = [
            quest for quest in quests.completed_shinies
            if normalize_item_name(quest).lower() != normalized_shiny
        ]

    return {
        "removed_completed_items": removed_completed_items,
        "removed_completed_shinies": removed_completed_shinies,
        "removed_completed_skins": removed_completed_skins,
        "changed": bool(removed_completed_items or removed_completed_shinies or removed_completed_skins),
    }


def reset_player_quests(
    player_data: PlayerData,
    sections: set[str] | None = None,
    target_item_quests: int = DEFAULT_REGULAR_QUEST_TARGET,
    target_shiny_quests: int = DEFAULT_SHINY_QUEST_TARGET,
    target_skin_quests: int = DEFAULT_SKIN_QUEST_TARGET,
) -> dict:
    quests = player_data.quests
    target_sections = sections or set(RESETTABLE_QUEST_SECTIONS)
    invalid_sections = sorted(target_sections - RESETTABLE_QUEST_SECTIONS)
    if invalid_sections:
        raise ValueError(
            "❌ Invalid quest sections: "
            + ", ".join(invalid_sections)
            + ". Valid options: current_items, current_shinies, current_skins, completed_items, completed_shinies, completed_skins, all"
        )

    reset_sections = []

    if "current_items" in target_sections:
        quests.current_items.clear()
        reset_sections.append("current_items")
    if "current_shinies" in target_sections:
        quests.current_shinies.clear()
        reset_sections.append("current_shinies")
    if "current_skins" in target_sections:
        quests.current_skins.clear()
        reset_sections.append("current_skins")
    if "completed_items" in target_sections:
        quests.completed_items.clear()
        reset_sections.append("completed_items")
    if "completed_shinies" in target_sections:
        quests.completed_shinies.clear()
        reset_sections.append("completed_shinies")
    if "completed_skins" in target_sections:
        quests.completed_skins.clear()
        reset_sections.append("completed_skins")

    refill_changed = refresh_player_quests(
        player_data,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )

    return {
        "reset_sections": reset_sections,
        "refill_changed": refill_changed,
    }


def apply_quest_targets(
    player_data: PlayerData,
    *,
    target_item_quests: int,
    target_shiny_quests: int,
    target_skin_quests: int,
) -> dict:
    quests = player_data.quests

    removed_current_items = quests.current_items[target_item_quests:]
    removed_current_shinies = quests.current_shinies[target_shiny_quests:]
    removed_current_skins = quests.current_skins[target_skin_quests:]

    if removed_current_items:
        quests.current_items = quests.current_items[:target_item_quests]
    if removed_current_shinies:
        quests.current_shinies = quests.current_shinies[:target_shiny_quests]
    if removed_current_skins:
        quests.current_skins = quests.current_skins[:target_skin_quests]

    refill_changed = refresh_player_quests(
        player_data,
        target_item_quests=target_item_quests,
        target_shiny_quests=target_shiny_quests,
        target_skin_quests=target_skin_quests,
    )

    return {
        "removed_current_items": removed_current_items,
        "removed_current_shinies": removed_current_shinies,
        "removed_current_skins": removed_current_skins,
        "refill_changed": refill_changed,
        "changed": bool(removed_current_items or removed_current_shinies or removed_current_skins or refill_changed),
    }
