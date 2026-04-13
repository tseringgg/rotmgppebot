"""Utilities for managing item sets and set completion detection."""

import csv
import re
from functools import lru_cache
from typing import Dict, List, Optional, Set
from dataclass import PPEData


# Unicode normalization patterns (consistent with calc_points.py)
_APOSTROPHE_VARIANTS = "\u2018\u2019\u02bc\u2032\u00b4`"
_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"

ITEM_SETS_CSV = "./rotmg_item_sets.csv"


def normalize_item_name(name: str) -> str:
    """Normalize item names for robust cross-source matching."""
    if not name:
        return ""
    normalized = name

    # Normalize typographic apostrophes to plain ASCII apostrophe.
    for apostrophe in _APOSTROPHE_VARIANTS:
        normalized = normalized.replace(apostrophe, "'")

    # Normalize unicode dash/minus variants to a standard hyphen.
    for dash in _DASH_VARIANTS:
        normalized = normalized.replace(dash, "-")

    # Treat spacing around hyphens as cosmetic formatting differences.
    normalized = re.sub(r"\s*-\s*", "-", normalized)

    normalized = " ".join(normalized.split())
    return normalized.strip()


@lru_cache(maxsize=1)
def load_item_sets() -> Dict[str, Dict[str, List[str]]]:
    """Load item sets from CSV. Returns dict: set_name -> {'type': 'ST'|'UT', 'items': [item1, item2, ...]}"""
    sets: Dict[str, Dict[str, any]] = {}
    try:
        with open(ITEM_SETS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Extract set information
                weapon = row.get("Weapon Name", "").strip()
                ability = row.get("Ability Name", "").strip()
                armor = row.get("Armor Name", "").strip()
                ring = row.get("Ring Name", "").strip()
                set_name = row.get("Set Name", "").strip()
                set_type = row.get("Type", "ST").strip().upper()

                # Skip incomplete entries
                if not all([weapon, ability, armor, ring, set_name]):
                    continue

                # Normalize all item names and set name
                normalized_items = [
                    normalize_item_name(weapon),
                    normalize_item_name(ability),
                    normalize_item_name(armor),
                    normalize_item_name(ring),
                ]

                # Ensure all items are non-empty after normalization
                if not all(normalized_items):
                    continue

                # Validate set type
                if set_type not in {"ST", "UT"}:
                    set_type = "ST"

                sets[set_name] = {
                    "type": set_type,
                    "items": normalized_items,
                }
    except FileNotFoundError:
        pass

    return sets


def get_all_sets() -> Dict[str, Dict[str, any]]:
    """Get all loaded item sets."""
    return load_item_sets()


def get_sets_by_type(set_type: str) -> Dict[str, List[str]]:
    """Get all sets of a specific type (ST or UT). Returns dict: set_name -> items_list."""
    all_sets = load_item_sets()
    filtered = {}
    for set_name, set_data in all_sets.items():
        if set_data["type"] == set_type.upper():
            filtered[set_name] = set_data["items"]
    return filtered


def check_set_completion(ppe: PPEData, set_items: List[str]) -> bool:
    """
    Check if a PPE has all items in a set.
    
    Args:
        ppe: PPEData object to check
        set_items: List of normalized item names required for the set
    
    Returns:
        True if all items in the set are present in the PPE's loot
    """
    # Collect all items in the PPE (non-shiny only for set completion)
    ppe_items: Set[str] = set()
    for loot in ppe.loot:
        if loot.quantity > 0:
            normalized = normalize_item_name(loot.item_name)
            ppe_items.add(normalized)

    # Check if all set items are present
    return all(item in ppe_items for item in set_items)


def find_completed_sets(ppe: PPEData) -> List[str]:
    """
    Find all sets that are completed by the PPE.
    
    Args:
        ppe: PPEData object to check
    
    Returns:
        List of set names that are fully completed
    """
    all_sets = load_item_sets()
    completed: List[str] = []

    for set_name, set_data in all_sets.items():
        if check_set_completion(ppe, set_data["items"]):
            completed.append(set_name)

    return completed


def get_newly_completed_sets(ppe: PPEData, previously_completed: List[str]) -> List[tuple[str, str]]:
    """
    Get sets that were just completed by the PPE.
    
    Args:
        ppe: PPEData object to check
        previously_completed: List of set names that were already completed
    
    Returns:
        List of tuples: (set_name, set_type) for newly completed sets
    """
    currently_completed = find_completed_sets(ppe)
    all_sets = load_item_sets()
    newly_completed = []

    for set_name in currently_completed:
        if set_name not in previously_completed:
            set_type = all_sets[set_name]["type"]
            newly_completed.append((set_name, set_type))

    return newly_completed


def get_no_longer_completed_sets(ppe: PPEData, previously_completed: List[str]) -> List[tuple[str, str]]:
    """
    Get sets that are no longer completed by the PPE.
    
    Args:
        ppe: PPEData object to check
        previously_completed: List of set names that were previously completed
    
    Returns:
        List of tuples: (set_name, set_type) for sets that are no longer completed
    """
    currently_completed = find_completed_sets(ppe)
    all_sets = load_item_sets()
    no_longer_completed = []

    for set_name in previously_completed:
        if set_name not in currently_completed:
            set_type = all_sets.get(set_name, {}).get("type", "Unknown")
            no_longer_completed.append((set_name, set_type))

    return no_longer_completed
