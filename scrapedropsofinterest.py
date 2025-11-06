import pandas as pd
from bs4 import BeautifulSoup

# === Configuration ===
HTML_FILE = "ancient_ruins.html"          # Dungeon HTML file
LOOT_TABLE_FILE = "rotmg_loot_drops.csv"  # Your master list
DIFFICULTY = 3                            # Ancient Ruins difficulty
DUNGEON_NAME = "Ancient Ruins"            # Optional (for logging only)


def extract_drops_of_interest(html_text):
    """Extracts all item names from the 'Drops of Interest' section."""
    soup = BeautifulSoup(html_text, "html.parser")
    header = soup.find("h2", id="interest")
    if not header:
        print("[!] Could not find 'Drops of Interest' section.")
        return []

    table = header.find_next("table")
    if not table:
        print("[!] No table found after Drops of Interest section.")
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
    # Load master loot table
    loot_df = pd.read_csv(LOOT_TABLE_FILE)

    # Add a Points column if missing
    if "Points" not in loot_df.columns:
        loot_df["Points"] = 0.0

    # Normalize names for matching
    loot_df["Item Name Lower"] = loot_df["Item Name"].str.lower().str.strip()

    # Load dungeon HTML
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html_text = f.read()

    drops = extract_drops_of_interest(html_text)
    print(f"[+] Found {len(drops)} drops in {DUNGEON_NAME}.")

    matched = 0
    for drop in drops:
        drop_clean = drop.lower().strip()
        match = loot_df["Item Name Lower"] == drop_clean
        if match.any():
            loot_df.loc[match, "Points"] += DIFFICULTY
            matched += 1

    print(f"[✓] Updated {matched} items with +{DIFFICULTY} points from {DUNGEON_NAME}.")

    # Clean up helper column
    loot_df = loot_df.drop(columns=["Item Name Lower"])

    # Save changes back to the same CSV
    loot_df.to_csv(LOOT_TABLE_FILE, index=False, encoding="utf-8")
    print(f"[✓] Saved updates to {LOOT_TABLE_FILE}")


if __name__ == "__main__":
    main()
