
LOOT_POINTS_CSV = "./rotmg_loot_drops_updated.csv"
import csv

import discord
PLAYER_RECORD_FILE = "./guild_loot_records.json"
from utils.player_records import get_item_from_ppe, load_player_records, save_player_records

# --- Load points table from CSV ---
def load_loot_points():
    loot_points = {}
    with open(LOOT_POINTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Item Name"].strip()
            points = float(row["Points"])
            loot_points[name] = points
    return loot_points




def calc_points(item: str, divine: bool, shiny: bool) -> float:
    loot_points = load_loot_points()

    # Get base points from CSV
    if shiny:
        base_points = loot_points.get(item + " (shiny)", 0)
    else:
        base_points = loot_points.get(item, 0)
    
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