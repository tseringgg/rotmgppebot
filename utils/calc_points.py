
LOOT_POINTS_CSV = "./rotmg_loot_drops_updated.csv"
import csv
PLAYER_RECORD_FILE = "./guild_loot_records.json"
from utils.player_records import load_player_records, save_player_records

# --- Load points table from CSV ---
def load_loot_points():
    loot_points = {}
    with open(LOOT_POINTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Item Name"].strip().lower()
            points = float(row["Points"])
            loot_points[name] = points
    return loot_points


async def calculate_loot_points(guild_id, player_name, detected_items):
    loot_points = load_loot_points()
    
    # guild_id = ctx.guild.id
    records = await load_player_records(guild_id)
    key = player_name.lower()

    if key not in records or not records[key].get("is_member", False):
        raise ValueError(f"{player_name} is not a contest member.")

    player_data = records[key]
    active_id = player_data.get("active_ppe")
    if not active_id:
        raise ValueError(f"{player_name} has no active PPE.")

    # --- get active PPE object ---
    active_ppe = next((p for p in player_data["ppes"] if p["id"] == active_id), None)
    if not active_ppe:
        raise ValueError(f"Active PPE (#{active_id}) not found for {player_name}.")

    results = []

    for item in detected_items:
        item_name = item["item"].lower()
        base_points = loot_points.get(item_name, 0)

        # Skip items with no point value
        if base_points <= 0:
            continue

        if base_points != 1:

            # --- check duplicate inside this PPE's item list ---
            existing_items = [i.lower() for i in active_ppe.get("items", [])]
            is_duplicate = item_name in existing_items
            final_points = base_points / 2 if is_duplicate else base_points

            # --- round down to nearest 0.5 ---
            import math
            final_points = math.floor(final_points * 2) / 2
        else:
            is_duplicate = False
            final_points = 1

        # --- update PPE items + points ---
        if not is_duplicate:
            active_ppe.setdefault("items", []).append(item_name)
        active_ppe["points"] = active_ppe.get("points", 0) + final_points

        results.append({
            "item": item["item"],
            "points": final_points,
            "duplicate": is_duplicate
        })

    
    await save_player_records(guild_id=guild_id, records=records)
    return results, active_ppe["points"]