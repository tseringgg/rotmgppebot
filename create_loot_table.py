import os
import math
from PIL import Image, ImageEnhance
import csv

def find_item_image(item_name, dungeons_path):
    """
    Search for an item's PNG file across all dungeon folders.
    Returns the path if found, None otherwise.
    """
    # Normalize apostrophes in the search name
    normalized_name = item_name.replace("'", "'").replace("'", "'")
    
    # Search in all dungeon subdirectories
    for dungeon_folder in os.listdir(dungeons_path):
        dungeon_path = os.path.join(dungeons_path, dungeon_folder)
        
        if not os.path.isdir(dungeon_path):
            continue
        
        # Check if this folder should be ignored
        if dungeon_folder in {"Forging", "Tiered Garbage", "_misc"}:
            continue
        
        # Try to find the PNG file with the normalized name
        png_path = os.path.join(dungeon_path, f"{normalized_name}.png")
        if os.path.exists(png_path):
            return png_path
    
    return None

def create_loot_images_from_csv():
    """
    Create 4 different loot background images and CSV mappings based on item order from rotmg_loot_drops_updated.csv:
    1. Normal items (excluding Skin, Limited, and Item)
    2. Normal items + Skins
    3. Normal items + Limited
    4. All items (Normal + Skins + Limited + Item)
    """
    
    # Paths
    dungeons_path = "dungeons"
    csv_file = "rotmg_loot_drops_updated.csv"
    target_size = (40, 40)
    
    if not os.path.exists(dungeons_path):
        print(f"Error: '{dungeons_path}' folder not found!")
        return
    
    if not os.path.exists(csv_file):
        print(f"Error: '{csv_file}' not found!")
        return
    
    # Read the CSV file and load items in order
    all_items = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_name = row["Item Name"].strip()
                loot_type = row["Loot Type"].strip()
                
                if not item_name or not loot_type:
                    continue
                
                all_items.append({
                    'name': item_name,
                    'loot_type': loot_type
                })
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    print(f"Loaded {len(all_items)} items from CSV")
    
    # Separate items into categories
    normal_items = []  # Excludes Skin, Limited, and Item
    skin_items = []
    limited_items = []
    item_type_items = []
    all_loaded_items = []
    
    missing_items = []
    
    for item in all_items:
        item_name = item['name']
        loot_type = item['loot_type']
        
        # Find the image file
        img_path = find_item_image(item_name, dungeons_path)
        
        if img_path is None:
            missing_items.append((item_name, loot_type))
            continue
        
        try:
            # Load and process the image
            img = Image.open(img_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            
            # Create grayed-out silhouette
            gray_img = create_gray_silhouette(img)
            
            # Categorize the item
            if loot_type == "Skin":
                skin_items.append((gray_img, item_name))
                all_loaded_items.append((gray_img, item_name))
            elif loot_type == "Limited":
                limited_items.append((gray_img, item_name))
                all_loaded_items.append((gray_img, item_name))
            elif loot_type == "Item":
                # 'Item' type should only appear in the all variant.
                item_type_items.append((gray_img, item_name))
                all_loaded_items.append((gray_img, item_name))
            else:
                normal_items.append((gray_img, item_name))
                all_loaded_items.append((gray_img, item_name))
            
        except Exception as e:
            print(f"Error loading {img_path}: {e}")
            missing_items.append((item_name, loot_type))
    
    # Create 4 image variants
    variants = [
        ("normal", normal_items),
        ("normal_skins", normal_items + skin_items),
        ("normal_limited", normal_items + limited_items),
        ("all", all_loaded_items)
    ]
    
    for variant_name, items in variants:
        if not items:
            print(f"⚠️  No items for variant '{variant_name}'")
            continue
        
        create_loot_background_image(items, variant_name, target_size)
    
    # Print missing items
    print("\n" + "="*60)
    if missing_items:
        print(f"❌ {len(missing_items)} items missing images:")
        for item_name, loot_type in missing_items:
            print(f"  - {item_name} ({loot_type})")
    else:
        print("✅ All items have images!")
    print("="*60)

def create_loot_background_image(items, variant_name, target_size):
    """
    Create a single loot background image and CSV mapping for a variant.
    """
    num_images = len(items)
    
    # Calculate grid dimensions
    grid_cols = math.ceil(math.sqrt(num_images))
    grid_rows = math.ceil(num_images / grid_cols)
    
    print(f"\n📊 Creating '{variant_name}' variant:")
    print(f"   {num_images} items in {grid_cols}x{grid_rows} grid")
    
    # Create the background image
    total_width = grid_cols * target_size[0]
    total_height = grid_rows * target_size[1]
    background_image = Image.new('RGBA', (total_width, total_height), (255, 255, 255, 0))
    
    sprite_mapping = []
    
    # Place images in grid and record positions
    for i, (img, item_name) in enumerate(items):
        row = i // grid_cols
        col = i % grid_cols
        
        x = col * target_size[0]
        y = row * target_size[1]
        
        # Place the grayed-out image
        background_image.paste(img, (x, y), img)
        
        # Record the mapping
        sprite_mapping.append({
            'item_name': item_name,
            'grid_x': col,
            'grid_y': row,
            'pixel_x': x,
            'pixel_y': y
        })
    
    # Save the background image
    background_path = f"loot_background_{variant_name}.png"
    background_image.save(background_path, "PNG")
    print(f"   ✅ Image saved: {background_path} ({total_width}x{total_height}px)")
    
    # Save the mapping CSV
    csv_path = f"sprite_positions_{variant_name}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['item_name', 'grid_x', 'grid_y', 'pixel_x', 'pixel_y']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sprite_mapping)
    
    print(f"   ✅ Mapping saved: {csv_path}")

def create_loot_background_and_mapping():
    """
    Legacy function - now calls the new CSV-based creation function
    """
    return create_loot_images_from_csv()

def create_gray_silhouette(img):
    """
    Convert an image to a grayed-out silhouette while preserving the shape.
    """
    # Create a copy to work with
    silhouette = img.copy()
    
    # Convert to grayscale but keep alpha channel
    grayscale = silhouette.convert('LA')  # Luminance + Alpha
    
    # Convert back to RGBA
    silhouette = grayscale.convert('RGBA')
    
    # Make it darker/more gray
    enhancer = ImageEnhance.Brightness(silhouette)
    silhouette = enhancer.enhance(0.3)  # Make it darker
    
    # Apply the original alpha channel to maintain transparency
    original_alpha = img.split()[-1]  # Get alpha channel
    r, g, b, _ = silhouette.split()
    silhouette = Image.merge('RGBA', (r, g, b, original_alpha))
    
    return silhouette


if __name__ == "__main__":
    create_loot_images_from_csv()