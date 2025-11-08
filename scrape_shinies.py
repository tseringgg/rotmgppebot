import os
from bs4 import BeautifulSoup
import csv

# Path to your downloaded HTML file
HTML_FILE = "rotmg_shinies.html"
OUTPUT_CSV = "shiny_items.csv"

def scrape_shiny_items():
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    shiny_data = []

    # Find all tables that contain loot data
    for table in soup.find_all("table", class_="table"):
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue  # skip headers or incomplete rows

            item_name_tag = cols[0].find("a")
            shiny_col = cols[2]  # Shiny Variant column

            # Check if there's a shiny variant image
            shiny_img = shiny_col.find("img")
            if shiny_img:
                item_name = item_name_tag.text.strip() if item_name_tag else "Unknown"
                shiny_img_url = shiny_img.get("src")
                drop_location = cols[3].text.strip() if len(cols) > 3 else "Unknown"

                shiny_data.append({
                    "Item Name": item_name,
                    "Shiny Name": f"Shiny {item_name}",
                    "Shiny Image URL": shiny_img_url,
                    "Drop Location": drop_location
                })

    # Save to CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Item Name", "Shiny Name", "Shiny Image URL", "Drop Location"])
        writer.writeheader()
        writer.writerows(shiny_data)

    print(f"✅ Extracted {len(shiny_data)} shiny items → {OUTPUT_CSV}")

if __name__ == "__main__":
    scrape_shiny_items()
