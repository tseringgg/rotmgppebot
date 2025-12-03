
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




async def calc_points(interaction: discord.Interaction, item: str, divine: bool, shiny: bool) -> float:
    loot_points = load_loot_points()
    key = interaction.user.id
    if interaction.guild is None:
            raise ValueError("Interaction guild is None.")
    guild_id = interaction.guild.id
    player_name = interaction.user.display_name

    records = await load_player_records(interaction)


    if key not in records:
        raise ValueError(f"Player record for {player_name} not found.")
    if not records[key].is_member:
        raise ValueError(f"{player_name} is not a contest member.")

    player_data = records[key]
    active_id = player_data.active_ppe
    if not active_id:
        raise ValueError(f"{player_name} has no active PPE.")

    # --- get active PPE object ---
    active_ppe = next((p for p in player_data.ppes if p.id == active_id), None)
    if not active_ppe:
        raise ValueError(f"Active PPE (#{active_id}) not found for {player_name}.")

    item_name = item
    # if divine:
    #     item_name = item_name + "(divine)"

    # maybe send message if item not found?
    if shiny:
        base_points = loot_points.get(item_name + " (shiny)", 0)
    else:
        base_points = loot_points.get(item_name, 0)
    

    item_name = get_item_from_ppe(active_ppe, item_name, divine, shiny)
    if base_points <= 0:
        return 0.0
    
    is_duplicate = item_name is None

    if base_points != 1:
        final_points = base_points / 2 if is_duplicate else base_points
    else:
        final_points = 1.0

    if divine:
        final_points = final_points * 2

    # --- round down to nearest 0.5 ---
    import math
    final_points = math.floor(final_points * 2) / 2

    return final_points