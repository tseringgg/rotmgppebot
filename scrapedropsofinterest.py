import os
import pandas as pd
from bs4 import BeautifulSoup

# === Configuration ===
HTML_FOLDER = "dungeon_htmls"             # Folder with dungeon HTMLs
LOOT_TABLE_FILE = "rotmg_loot_drops.csv"  # Your master loot table
DUNGEONS_FILE = "dungeon_difficulty.csv"            # Dungeon name + difficulty (no header row!)

def extract_drops_of_interest(html_text):
    """Extracts all item names from the 'Drops of Interest' section."""
    soup = BeautifulSoup(html_text, "html.parser")
    header = soup.find("h2", string="Drops of Interest")
    if not header:
        header = soup.find("h3", string="Drops of Interest")

    if not header:
        return []

    table = header.find_next("table")
    if not table:
        return []

    drops = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        first_td = tds[0]
        imgs = first_td.find_all("img", alt=True)
        for img in imgs:
            drops.append(img["alt"].strip())
    return drops


def main():
    # === Load master loot table ===
    loot_df = pd.read_csv(LOOT_TABLE_FILE)

    # Ensure Points column exists and initialize all to 10
    loot_df["Points"] = 10.0
    loot_df["Item Name Lower"] = loot_df["Item Name"].str.lower().str.strip()

    # === Load dungeon difficulties (no header in your file) ===
    dungeons_df = pd.read_csv(DUNGEONS_FILE, header=None, names=["Dungeon Name", "Difficulty"])
    dungeons_df["Dungeon Name Lower"] = dungeons_df["Dungeon Name"].str.lower().str.strip()

    total_updated = 0

    # === Process every dungeon HTML file ===
    for file in os.listdir(HTML_FOLDER):
        if not file.endswith(".html"):
            continue

        dungeon_name = os.path.splitext(file)[0].replace("_", " ").strip().lower()
        match = dungeons_df["Dungeon Name Lower"] == dungeon_name
        if not match.any():
            print(f"[!] Skipping {file}: no difficulty found in dungeons.csv")
            continue

        difficulty = float(dungeons_df.loc[match, "Difficulty"].iloc[0])

        path = os.path.join(HTML_FOLDER, file)
        with open(path, "r", encoding="utf-8") as f:
            html_text = f.read()

        drops = extract_drops_of_interest(html_text)
        if not drops:
            print(f"[!] No drops found for {file}")
            continue

        matched = 0
        for drop in drops:
            drop_clean = drop.lower().strip()
            loot_match = loot_df["Item Name Lower"] == drop_clean
            if loot_match.any():
                loot_df.loc[loot_match, "Points"] = difficulty  # Update points to dungeon difficulty, NOT add
                matched += 1

        total_updated += matched
        print(f"[✓] {file}: matched {matched} drops (+{difficulty} points each)")

    # === Save updates ===
    loot_df.drop(columns=["Item Name Lower"], inplace=True)
    loot_df.to_csv(LOOT_TABLE_FILE, index=False, encoding="utf-8")

    print(f"\n[✓] Initialized all drops to 10 points.")
    print(f"[✓] Updated {total_updated} total items with dungeon difficulty points.")
    print(f"[✓] Saved changes to {LOOT_TABLE_FILE}")

if __name__ == "__main__":
    main()
