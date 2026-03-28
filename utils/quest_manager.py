import csv
import random
from typing import Dict, List, Tuple

from dataclass import PlayerData
from utils.calc_points import load_loot_points, normalize_item_name

_LOOT_CSV = "rotmg_loot_drops_updated.csv"
_REGULAR_BY_NORM: Dict[str, str] = {}
_SHINY_BY_NORM: Dict[str, str] = {}
_SKIN_BY_NORM: Dict[str, str] = {}
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
    for item_name, _shiny in player_data.unique_items:
        owned.add(normalize_item_name(item_name).lower())
    return owned


def _owned_shiny_target_norms(player_data: PlayerData) -> set[str]:
    owned = set()
    for item_name, shiny in player_data.unique_items:
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
) -> bool:
    sanitized = _sanitize_quest_buckets(player_data)

    if _is_global_mode_enabled(global_quests):
        return bool(sanitized or _apply_global_quests_mode(player_data, global_quests))

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
) -> dict:
    sanitized = _sanitize_quest_buckets(player_data)
    if _is_global_mode_enabled(global_quests):
        initialized = _apply_global_quests_mode(player_data, global_quests)
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
        if normalize_item_name(quest).lower() == normalized_regular:
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
        if normalize_item_name(quest).lower() == normalized_regular:
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
        if normalize_item_name(quest).lower() == normalized_regular
    ]
    removed_completed_skins = [
        quest for quest in quests.completed_skins
        if normalize_item_name(quest).lower() == normalized_regular
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
