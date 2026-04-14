"""Utilities for calc points."""

LOOT_POINTS_CSV = "./rotmg_loot_drops_updated.csv"
import csv
import re
from functools import lru_cache

import discord
PLAYER_RECORD_FILE = "./guild_loot_records.json"
from utils.guild_config import get_rarity_multipliers
from utils.loot_constants import normalize_rarity

_APOSTROPHE_VARIANTS = "\u2018\u2019\u02bc\u2032\u00b4`"
_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


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
def _load_loot_entries():
    loot_entries = {}
    with open(LOOT_POINTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_name_raw = row.get("Item Name")
            points_raw = row.get("Points")
            loot_type_raw = row.get("Loot Type", "")
            # Skip rows with missing columns (empty rows in CSV)
            if item_name_raw is None or points_raw is None:
                continue
            item_name = item_name_raw.strip()
            points_str = points_raw.strip()
            if not item_name or not points_str:
                continue
            name = normalize_item_name(item_name)
            points = float(points_str)
            loot_entries[name] = {
                "points": points,
                "loot_type": str(loot_type_raw).strip().lower(),
            }
    return loot_entries


# --- Load points table from CSV ---
@lru_cache(maxsize=1)
def load_loot_points():
    return {name: float(entry["points"]) for name, entry in _load_loot_entries().items()}


@lru_cache(maxsize=1)
def load_loot_types():
    return {name: str(entry["loot_type"]) for name, entry in _load_loot_entries().items()}




def calc_points(item: str, shiny: bool, rarity: str = "common", guild_config: dict | None = None) -> float:
    loot_points = load_loot_points()
    normalized_item = normalize_item_name(item)

    # Get base points from CSV
    if shiny:
        base_points = loot_points.get(f"{normalized_item} (shiny)", 0)
    else:
        base_points = loot_points.get(normalized_item, 0)
    
    if base_points <= 0:
        return 0.0
    
    effective_rarity = normalize_rarity(rarity)
    rarity_multipliers = get_rarity_multipliers(guild_config or {})
    final_points = base_points * rarity_multipliers.get(effective_rarity, 1.0)

    # Round down to nearest 0.5
    import math
    final_points = math.floor(final_points * 2) / 2

    return final_points