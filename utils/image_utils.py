"""Image utility functions for processing and enhancing images."""

import os
import tempfile

from PIL import Image

from utils.calc_points import normalize_item_name
from utils.item_image_index import get_item_image_index

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RARITY_PICS_DIR = os.path.join(_PROJECT_ROOT, "helper_pics", "rarity_pics")
_DUNGEONS_PATH = os.path.join(_PROJECT_ROOT, "helper_pics", "dungeon_pics")


def _item_image_index() -> dict[str, str]:
    return get_item_image_index(_DUNGEONS_PATH)


def resolve_item_image_path(item_name: str, shiny: bool = False) -> str | None:
    base = item_name.strip()
    if not base:
        return None

    candidates = [base]
    if shiny and not base.lower().endswith("(shiny)"):
        candidates.insert(0, f"{base} (shiny)")

    index = _item_image_index()
    for candidate in candidates:
        key = normalize_item_name(candidate).lower()
        path = index.get(key)
        if path:
            return path
    return None


def overlay_rarity_badge_on_image(
    item_img: Image.Image,
    rarity: str,
    output_size: tuple[int, int] | None = None,
) -> Image.Image | None:
    rarity_normalized = str(rarity).strip().lower()
    if rarity_normalized == "common":
        return item_img.copy()

    rarity_file = f"{rarity_normalized}.png"
    rarity_image_path = os.path.join(_RARITY_PICS_DIR, rarity_file)
    if not os.path.exists(rarity_image_path):
        return None

    rarity_img = Image.open(rarity_image_path).convert("RGBA")
    item_rgba = item_img.convert("RGBA")

    if output_size:
        target_width, target_height = output_size
        if rarity_normalized == "uncommon":
            target_width = max(1, target_width // 2)
            target_height = max(1, target_height // 2)
        rarity_img = rarity_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    else:
        scale_factor = 0.15 if rarity_normalized == "uncommon" else 0.30
        new_width = max(10, int(item_rgba.width * scale_factor))
        aspect_ratio = rarity_img.height / rarity_img.width
        new_height = int(new_width * aspect_ratio)
        rarity_img = rarity_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    margin = 3
    x_pos = item_rgba.width - rarity_img.width - margin
    y_pos = item_rgba.height - rarity_img.height - margin
    item_rgba.paste(rarity_img, (x_pos, y_pos), rarity_img)
    if item_img.mode == "RGB":
        return item_rgba.convert("RGB")
    return item_rgba

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
        result_img = overlay_rarity_badge_on_image(item_img, rarity, output_size=output_size)
        if result_img is None:
            return None
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        result_img.save(temp_path)
        return temp_path
        
    except Exception as e:
        print(f"[IMAGE_UTILS] Failed to overlay rarity badge: {e}")
        return None