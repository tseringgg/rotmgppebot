import os
import math
from PIL import Image, ImageEnhance
import glob
import csv

def create_loot_background_and_mapping():
    """
    Create a background PNG with grayed-out item silhouettes and a CSV mapping
    of item names to grid positions for the shareloot command system.
    """
    
    # Find all PNG files in dungeons folder and subfolders
    png_files = []
    dungeons_path = "dungeons"
    
    # Folders to ignore
    ignored_folders = {"Forging", "Tiered Garbage", "_misc"}
    
    if not os.path.exists(dungeons_path):
        print(f"Error: '{dungeons_path}' folder not found!")
        return
    
    # Use glob to find all PNG files recursively
    pattern = os.path.join(dungeons_path, "**", "*.png")
    all_png_files = glob.glob(pattern, recursive=True)
    
    # Filter out files from ignored folders
    for png_file in all_png_files:
        # Get the relative path from dungeons folder
        rel_path = os.path.relpath(png_file, dungeons_path)
        folder_parts = rel_path.split(os.sep)
        
        # Check if any part of the path matches ignored folders
        if not any(part in ignored_folders for part in folder_parts):
            png_files.append(png_file)

    if not png_files:
        print(f"No PNG files found in '{dungeons_path}' folder (after filtering)!")
        return
    
    print(f"Found {len(png_files)} PNG files (filtered)")
    
    # Load all images and create grayed-out versions
    images = []
    target_size = (40, 40)  # Standard size for all images
    seen_images = {}  # Track duplicates by image hash
    sprite_mapping = []  # Store name -> grid position mapping
    
    for png_file in png_files:
        try:
            img = Image.open(png_file)
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize to 40x40 if not already that size
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
                print(f"Resized: {os.path.basename(png_file)} to 40x40")
            
            # Create a simple hash of the image data to detect duplicates
            img_hash = hash(img.tobytes())
            
            if img_hash in seen_images:
                print(f"Skipping duplicate: {os.path.basename(png_file)} (same as {seen_images[img_hash]})")
                img.close()
                continue
            
            # Get item name from filename (remove .png extension)
            item_name = os.path.splitext(os.path.basename(png_file))[0]
            # Normalize apostrophes - convert curly to regular
            item_name = item_name.replace("'", "'").replace("'", "'")
            seen_images[img_hash] = item_name
            
            # Create grayed-out silhouette
            gray_img = create_gray_silhouette(img)
            images.append((gray_img, item_name))
            print(f"Loaded: {item_name} (40x40)")
        except Exception as e:
            print(f"Error loading {png_file}: {e}")

    if not images:
        print("No valid images loaded!")
        return
    
    # Calculate grid dimensions
    num_images = len(images)
    # Try to make a square-ish grid
    grid_cols = math.ceil(math.sqrt(num_images))
    grid_rows = math.ceil(num_images / grid_cols)
    
    print(f"Creating {grid_cols}x{grid_rows} grid for {num_images} images")
    print(f"Each cell will be {target_size[0]}x{target_size[1]} pixels")
    
    # Create the background image
    total_width = grid_cols * target_size[0]
    total_height = grid_rows * target_size[1]
    background_image = Image.new('RGBA', (total_width, total_height), (255, 255, 255, 0))
    
    # Place images in grid and record positions
    for i, (img, item_name) in enumerate(images):
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
    background_path = "loot_background.png"
    background_image.save(background_path, "PNG")
    print(f"✅ Loot background saved as '{background_path}'")
    print(f"Background dimensions: {total_width}x{total_height} pixels")
    
    # Save the mapping CSV
    csv_path = "sprite_positions.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['item_name', 'grid_x', 'grid_y', 'pixel_x', 'pixel_y']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sprite_mapping)
    
    print(f"✅ Sprite mapping saved as '{csv_path}'")
    print(f"Mapped {len(sprite_mapping)} unique items")
    
    # Clean up
    for img, _ in images:
        img.close()
    
    return background_path, csv_path

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

def create_loot_table():
    """
    Legacy function - now calls the new background creation function
    """
    return create_loot_background_and_mapping()

if __name__ == "__main__":
    create_loot_background_and_mapping()