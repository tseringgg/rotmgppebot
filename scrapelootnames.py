from bs4 import BeautifulSoup
import csv

HTML_FILE = "loot_containers.html"  # path to your saved HTML file

CLASS_NAMES = {
    "rogue", "wizard", "archer", "warrior", "priest",
    "knight", "paladin", "assassin", "necromancer",
    "huntress", "mystic", "trickster", "sorcerer",
    "ninja", "samurai", "bard", "summoner", "kensei"
}

def extract_loot_from_table(soup, bag_type):
    """Finds the loot table for a given bag type (e.g. 'Orange Bag', 'White Bag') and extracts all item titles."""
    img = soup.find("img", {"alt": bag_type})
    if not img:
        print(f"[!] Could not find image with alt='{bag_type}'.")
        return []

    # parent div holds the table
    parent_div = img.find_parent("div", class_="table-responsive")
    if not parent_div:
        print(f"[!] Could not locate table container for {bag_type}.")
        return []

    table = parent_div.find("table")
    if not table:
        print(f"[!] No <table> found under {bag_type} section.")
        return []

    drops = []
    for a in table.find_all("a", title=True):
        title = a["title"].strip()
        if title.lower() in CLASS_NAMES:
            continue
        drops.append(title)

    return drops

def main():
    print("[+] Loading local HTML file...")
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    print("[+] Extracting Orange Bag drops...")
    orange_drops = extract_loot_from_table(soup, "Orange Bag")
    print(f"    Found {len(orange_drops)} Orange Bag drops.")

    print("[+] Extracting White Bag drops...")
    white_drops = extract_loot_from_table(soup, "White Bag")
    print(f"    Found {len(white_drops)} White Bag drops.")

    all_rows = []
    for drop in orange_drops:
        all_rows.append({"Loot Type": "Set-Tiered (Orange Bag)", "Item Name": drop})
    for drop in white_drops:
        all_rows.append({"Loot Type": "White Bag", "Item Name": drop})

    output_file = "rotmg_loot_drops.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Loot Type", "Item Name"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"[✓] Saved {len(all_rows)} total drops to {output_file}")

if __name__ == "__main__":
    main()
