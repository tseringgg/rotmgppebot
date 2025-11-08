import csv
import unicodedata

LOOT_FILE = "rotmg_loot_drops.csv"
SHINY_FILE = "shiny_items.csv"
UPDATED_FILE = "rotmg_loot_drops_updated.csv"

def normalize_text(s: str):
    """Normalize text by converting smart quotes and trimming."""
    if not s:
        return ""
    # Convert fancy apostrophes/quotes to straight ones
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    # Normalize Unicode (handles subtle variants)
    s = unicodedata.normalize("NFKC", s)
    return s.strip()

def add_shiny_variants():
    # --- Load original loot data ---
    with open(LOOT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        loot_data = list(reader)

    points_lookup = {
        normalize_text(row["Item Name"]).lower(): (row["Loot Type"], float(row["Points"]))
        for row in loot_data
    }

    # --- Load shiny items ---
    with open(SHINY_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        shiny_items = list(reader)

    new_entries = []
    existing_names = {normalize_text(row["Item Name"]).lower() for row in loot_data}

    for shiny in shiny_items:
        base_name = normalize_text(shiny["Item Name"])
        lookup_key = base_name.lower()

        if lookup_key not in points_lookup:
            print(f"⚠️ Skipping {base_name}: not found in original loot table.")
            continue

        loot_type, points = points_lookup[lookup_key]
        shiny_name = f"{base_name} (shiny)"

        if shiny_name.lower() in existing_names:
            print(f"🔁 Skipping {shiny_name}: already in loot table.")
            continue

        new_entry = {
            "Loot Type": loot_type,
            "Item Name": shiny_name,
            "Points": str(int(points * 2))
        }
        new_entries.append(new_entry)
        existing_names.add(shiny_name.lower())
        print(f"✨ Added {shiny_name}: {points} → {points*2} points")

    updated = loot_data + new_entries

    with open(UPDATED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Loot Type", "Item Name", "Points"])
        writer.writeheader()
        writer.writerows(updated)

    print(f"✅ Added {len(new_entries)} shiny entries → {UPDATED_FILE}")

if __name__ == "__main__":
    add_shiny_variants()
