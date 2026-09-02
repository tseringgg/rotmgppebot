import csv

def find_unique_items(csv1_path, csv2_path):
    # Store items from the second CSV in a set for O(1) lookup speed
    csv2_items = set()
    
    try:
        with open(csv2_path, mode='r', encoding='utf-8') as f2:
            reader2 = csv.DictReader(f2)
            for row in reader2:
                # row.get() prevents KeyError if the row is malformed
                item_name = row.get('Item Name')
                if item_name and item_name.strip(): 
                    # .strip() removes accidental whitespace, ignoring "" rows
                    csv2_items.add(item_name.strip())
    except FileNotFoundError:
        print(f"Error: Could not find {csv2_path}")
        return

    unique_to_csv1 = []
    
    try:
        with open(csv1_path, mode='r', encoding='utf-8') as f1:
            reader1 = csv.DictReader(f1)
            for row in reader1:
                item_name = row.get('Item Name')
                if item_name and item_name.strip():
                    clean_name = item_name.strip()
                    # Check if the item is missing from the second CSV
                    if clean_name not in csv2_items:
                        unique_to_csv1.append(clean_name)
    except FileNotFoundError:
        print(f"Error: Could not find {csv1_path}")
        return

    # Output results
    if unique_to_csv1:
        print(f"Found {len(unique_to_csv1)} items in CSV 1 that are missing from CSV 2:\n")
        for item in unique_to_csv1:
            print(f"- {item}")
    else:
        print("No unique items found. CSV 2 contains all items from CSV 1.")

# === Usage Example ===
if __name__ == "__main__":
    # Replace these strings with your actual file paths
    file1 = 'other_file.csv'
    file2 = 'rotmg_loot_drops_updated.csv'
    
    find_unique_items(file1, file2)