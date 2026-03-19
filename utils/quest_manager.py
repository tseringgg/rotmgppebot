import csv
import random
from typing import Dict, List, Tuple

from dataclass import PlayerData
from utils.calc_points import normalize_item_name

_LOOT_CSV = "rotmg_loot_drops_updated.csv"
_REGULAR_BY_NORM: Dict[str, str] = {}
_SKIN_BY_NORM: Dict[str, str] = {}
_POOLS_LOADED = False
RESETTABLE_QUEST_SECTIONS = {
    "current_items",
    "current_skins",
    "completed_items",
    "completed_skins",
}


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

            normalized = normalize_item_name(item_name).lower()
            if loot_type == "skin":
                _SKIN_BY_NORM.setdefault(normalized, item_name)
            elif loot_type not in {"item", "limited", "skin"}:
                _REGULAR_BY_NORM.setdefault(normalized, item_name)

    _POOLS_LOADED = True


def _normalized_set(items: List[str]) -> set[str]:
    return {normalize_item_name(item).lower() for item in items}


def _contains_name(items: List[str], item_name: str) -> bool:
    target = normalize_item_name(item_name).lower()
    return any(normalize_item_name(item).lower() == target for item in items)


def _quest_target_name(item_name: str, shiny: bool = False) -> str:
    normalized = normalize_item_name(item_name)
    if shiny and not normalized.lower().endswith(" (shiny)"):
        return f"{normalized} (shiny)"
    return normalized


def _owned_normalized_items(player_data: PlayerData) -> set[str]:
    owned = set()
    for item_name, _shiny in player_data.unique_items:
        owned.add(normalize_item_name(item_name).lower())
    return owned


def _pick_random_from_pool(pool: Dict[str, str], blocked: set[str], count: int) -> List[str]:
    candidates = [display for norm, display in pool.items() if norm not in blocked]
    if not candidates or count <= 0:
        return []
    if len(candidates) <= count:
        random.shuffle(candidates)
        return candidates
    return random.sample(candidates, count)


def _fill_missing_quests(player_data: PlayerData, target_item_quests: int = 5, target_skin_quests: int = 1) -> Tuple[List[str], List[str]]:
    _load_quest_pools()
    quests = player_data.quests

    newly_added_items: List[str] = []
    newly_added_skins: List[str] = []

    owned = _owned_normalized_items(player_data)

    current_and_completed_items = _normalized_set(quests.current_items + quests.completed_items)
    blocked_item_norms = owned | current_and_completed_items

    item_slots = max(0, target_item_quests - len(quests.current_items))
    item_replacements = _pick_random_from_pool(_REGULAR_BY_NORM, blocked_item_norms, item_slots)
    for item in item_replacements:
        if not _contains_name(quests.current_items, item):
            quests.current_items.append(item)
            newly_added_items.append(item)

    current_and_completed_skins = _normalized_set(quests.current_skins + quests.completed_skins)
    blocked_skin_norms = owned | current_and_completed_skins

    skin_slots = max(0, target_skin_quests - len(quests.current_skins))
    skin_replacements = _pick_random_from_pool(_SKIN_BY_NORM, blocked_skin_norms, skin_slots)
    for skin in skin_replacements:
        if not _contains_name(quests.current_skins, skin):
            quests.current_skins.append(skin)
            newly_added_skins.append(skin)

    return newly_added_items, newly_added_skins


def initialize_quests_if_needed(player_data: PlayerData) -> bool:
    replacement_items, replacement_skins = _fill_missing_quests(player_data)
    return bool(replacement_items or replacement_skins)


def refresh_player_quests(player_data: PlayerData) -> bool:
    initialized = initialize_quests_if_needed(player_data)
    changed = initialized
    quests = player_data.quests

    owned = _owned_normalized_items(player_data)

    remaining_item_quests = []
    for quest in quests.current_items:
        if normalize_item_name(quest).lower() in owned:
            if not _contains_name(quests.completed_items, quest):
                quests.completed_items.append(quest)
            changed = True
        else:
            remaining_item_quests.append(quest)
    quests.current_items = remaining_item_quests

    remaining_skin_quests = []
    for quest in quests.current_skins:
        if normalize_item_name(quest).lower() in owned:
            if not _contains_name(quests.completed_skins, quest):
                quests.completed_skins.append(quest)
            changed = True
        else:
            remaining_skin_quests.append(quest)
    quests.current_skins = remaining_skin_quests

    replacement_items, replacement_skins = _fill_missing_quests(player_data)
    return bool(changed or replacement_items or replacement_skins)


def update_quests_for_item(player_data: PlayerData, item_name: str, shiny: bool = False) -> dict:
    initialized = initialize_quests_if_needed(player_data)
    normalized_item = normalize_item_name(_quest_target_name(item_name, shiny)).lower()
    quests = player_data.quests

    completed_items: List[str] = []
    completed_skins: List[str] = []

    remaining_item_quests = []
    for quest in quests.current_items:
        if normalize_item_name(quest).lower() == normalized_item:
            completed_items.append(quest)
            if not _contains_name(quests.completed_items, quest):
                quests.completed_items.append(quest)
        else:
            remaining_item_quests.append(quest)
    quests.current_items = remaining_item_quests

    remaining_skin_quests = []
    for quest in quests.current_skins:
        if normalize_item_name(quest).lower() == normalized_item:
            completed_skins.append(quest)
            if not _contains_name(quests.completed_skins, quest):
                quests.completed_skins.append(quest)
        else:
            remaining_skin_quests.append(quest)
    quests.current_skins = remaining_skin_quests

    replacement_items: List[str] = []
    replacement_skins: List[str] = []
    if completed_items or completed_skins or initialized:
        replacement_items, replacement_skins = _fill_missing_quests(player_data)

    return {
        "initialized": initialized,
        "completed_items": completed_items,
        "completed_skins": completed_skins,
        "replacement_items": replacement_items,
        "replacement_skins": replacement_skins,
        "changed": bool(initialized or completed_items or completed_skins or replacement_items or replacement_skins),
    }


def remove_item_from_completed_quests(player_data: PlayerData, item_name: str, shiny: bool = False) -> dict:
    """Remove matching item from completed quest lists after season-loot removal."""
    quests = player_data.quests
    normalized_item = normalize_item_name(_quest_target_name(item_name, shiny)).lower()

    removed_completed_items = [
        quest for quest in quests.completed_items
        if normalize_item_name(quest).lower() == normalized_item
    ]
    removed_completed_skins = [
        quest for quest in quests.completed_skins
        if normalize_item_name(quest).lower() == normalized_item
    ]

    if removed_completed_items:
        quests.completed_items = [
            quest for quest in quests.completed_items
            if normalize_item_name(quest).lower() != normalized_item
        ]
    if removed_completed_skins:
        quests.completed_skins = [
            quest for quest in quests.completed_skins
            if normalize_item_name(quest).lower() != normalized_item
        ]

    return {
        "removed_completed_items": removed_completed_items,
        "removed_completed_skins": removed_completed_skins,
        "changed": bool(removed_completed_items or removed_completed_skins),
    }


def reset_player_quests(player_data: PlayerData, sections: set[str] | None = None) -> dict:
    quests = player_data.quests
    target_sections = sections or set(RESETTABLE_QUEST_SECTIONS)
    invalid_sections = sorted(target_sections - RESETTABLE_QUEST_SECTIONS)
    if invalid_sections:
        raise ValueError(
            "❌ Invalid quest sections: "
            + ", ".join(invalid_sections)
            + ". Valid options: current_items, current_skins, completed_items, completed_skins, all"
        )

    reset_sections = []

    if "current_items" in target_sections:
        quests.current_items.clear()
        reset_sections.append("current_items")
    if "current_skins" in target_sections:
        quests.current_skins.clear()
        reset_sections.append("current_skins")
    if "completed_items" in target_sections:
        quests.completed_items.clear()
        reset_sections.append("completed_items")
    if "completed_skins" in target_sections:
        quests.completed_skins.clear()
        reset_sections.append("completed_skins")

    # Keep quest lists populated after resets that touch current quests.
    refill_changed = refresh_player_quests(player_data)

    return {
        "reset_sections": reset_sections,
        "refill_changed": refill_changed,
    }
