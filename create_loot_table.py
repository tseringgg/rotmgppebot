import os
import math
from PIL import Image
import glob

def create_loot_table():
    """
    Compile all PNG files from dungeons folder and subfolders into a grid layout
    and save as loot_table.png
    """
    
    # Find all PNG files in dungeons folder and subfolders
    png_files = []
    dungeons_path = "dungeons"
    
    if not os.path.exists(dungeons_path):
        print(f"Error: '{dungeons_path}' folder not found!")
        return
    
    # Use glob to find all PNG files recursively
    pattern = os.path.join(dungeons_path, "**", "*.png")
    png_files = glob.glob(pattern, recursive=True)
    
    if not png_files:
        print(f"No PNG files found in '{dungeons_path}' folder!")
        return
    
    print(f"Found {len(png_files)} PNG files")
    
    # Load all images and get their dimensions
    images = []
    max_width = 0
    max_height = 0
    
    for png_file in png_files:
        try:
            img = Image.open(png_file)
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            images.append(img)
            max_width = max(max_width, img.width)
            max_height = max(max_height, img.height)
            print(f"Loaded: {os.path.basename(png_file)} ({img.width}x{img.height})")
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
    print(f"Each cell will be {max_width}x{max_height} pixels")
    
    # Create the final image
    total_width = grid_cols * max_width
    total_height = grid_rows * max_height
    final_image = Image.new('RGBA', (total_width, total_height), (255, 255, 255, 0))
    
    # Place images in grid
    for i, img in enumerate(images):
        row = i // grid_cols
        col = i % grid_cols
        
        x = col * max_width
        y = row * max_height
        
        # Center the image in its cell if it's smaller than max dimensions
        x_offset = (max_width - img.width) // 2
        y_offset = (max_height - img.height) // 2
        
        final_image.paste(img, (x + x_offset, y + y_offset), img)
    
    # Save the final image
    output_path = "loot_table.png"
    final_image.save(output_path, "PNG")
    print(f"✅ Loot table saved as '{output_path}'")
    print(f"Final dimensions: {total_width}x{total_height} pixels")
    
    # Clean up
    for img in images:
        img.close()

if __name__ == "__main__":
    create_loot_table()