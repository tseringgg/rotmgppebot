
LOOT_POINTS_CSV = "./rotmg_loot_drops_updated.csv"
import csv

import discord
PLAYER_RECORD_FILE = "./guild_loot_records.json"
from utils.player_records import get_item_from_ppe, load_player_records, save_player_records

_APOSTROPHE_VARIANTS = "\u2018\u2019\u02bc\u2032\u00b4`"


def normalize_item_name(name: str) -> str:
    """Normalize item names for robust cross-source matching."""
    if not name:
        return ""
    normalized = name
    for apostrophe in _APOSTROPHE_VARIANTS:
        normalized = normalized.replace(apostrophe, "'")
    normalized = " ".join(normalized.split())
    return normalized.strip()

# --- Load points table from CSV ---
def load_loot_points():
    loot_points = {}
    with open(LOOT_POINTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = normalize_item_name(row["Item Name"])
            points = float(row["Points"])
            loot_points[name] = points
    return loot_points




def calc_points(item: str, divine: bool, shiny: bool) -> float:
    loot_points = load_loot_points()
    normalized_item = normalize_item_name(item)

    # Get base points from CSV
    if shiny:
        base_points = loot_points.get(f"{normalized_item} (shiny)", 0)
    else:
        base_points = loot_points.get(normalized_item, 0)
    
    if base_points <= 0:
        return 0.0
    
    # Apply divine multiplier
    final_points = base_points
    if divine:
        final_points = final_points * 2

    # Round down to nearest 0.5
    import math
    final_points = math.floor(final_points * 2) / 2

    return final_points