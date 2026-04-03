"""Image utility functions for processing and enhancing images."""

import os
import tempfile

from PIL import Image

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RARITY_PICS_DIR = os.path.join(_PROJECT_ROOT, "helper_pics", "rarity_pics")

def overlay_rarity_badge(
    item_image_path: str,
    rarity: str,
    output_size: tuple[int, int] | None = None
) -> str | None:
    """
    Overlay a rarity badge image on the bottom right of an item image.
    
    Args:
        item_image_path: Path to the item image
        rarity: Rarity level (common, uncommon, rare, legendary, divine)
        output_size: Optional size (width, height) to scale the rarity badge
    
    Returns:
        Path to the temporary image with overlay, or None if overlay fails
    """
    # Common items have no overlay
    if rarity.lower() == "common":
        return item_image_path
    
    try:
        # Load the item image
        if not os.path.exists(item_image_path):
            return None
        
        item_img = Image.open(item_image_path)
        
        # Construct path to rarity image
        rarity_file = f"{rarity.lower()}.png"
        rarity_image_path = os.path.join(_RARITY_PICS_DIR, rarity_file)
        
        if not os.path.exists(rarity_image_path):
            return None
        
        # Load the rarity image
        rarity_img = Image.open(rarity_image_path).convert("RGBA")
        
        # Scale the rarity badge while preserving aspect ratio
        if output_size:
            print(f"[IMAGE_UTILS] Scaling rarity badge to {output_size}")
            target_width, target_height = output_size
            
            # Halve the size for uncommon so the single diamond matches the scale of others
            if rarity.lower() == "uncommon":
                target_width = max(1, target_width // 2)
                target_height = max(1, target_height // 2)
                
            rarity_img = rarity_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            # Default: make badge width roughly 30% of item image width
            # Halve the scale factor for uncommon items (15% instead of 30%)
            scale_factor = 0.15 if rarity.lower() == "uncommon" else 0.30
            new_width = max(10, int(item_img.width * scale_factor))
            
            # Calculate the new height based on the original aspect ratio
            aspect_ratio = rarity_img.height / rarity_img.width
            new_height = int(new_width * aspect_ratio)
            
            rarity_img = rarity_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create a copy of the item image to preserve the original
        result_img = item_img.convert("RGBA")
        
        # Calculate position: bottom right with small margin
        margin = 3
        x_pos = result_img.width - rarity_img.width - margin
        y_pos = result_img.height - rarity_img.height - margin
        
        # Paste the rarity badge onto the item image
        result_img.paste(rarity_img, (x_pos, y_pos), rarity_img)
        
        # Convert back to RGB if original was RGB
        if item_img.mode == "RGB":
            result_img = result_img.convert("RGB")
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        result_img.save(temp_path)
        return temp_path
        
    except Exception as e:
        print(f"[IMAGE_UTILS] Failed to overlay rarity badge: {e}")
        return None