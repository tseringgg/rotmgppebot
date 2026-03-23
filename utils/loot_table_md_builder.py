import os
import tempfile
from datetime import datetime
from dataclass import PPEData
from utils.calc_points import load_loot_points
import math


def calculate_item_points(item_name: str, divine: bool, shiny: bool, quantity: int) -> float:
    """Calculate total points for an item based on its properties and quantity (duplicates)"""
    loot_points = load_loot_points()
    
    # Get base points from CSV
    if shiny:
        base_points = loot_points.get(item_name + " (shiny)", 0)
    else:
        base_points = loot_points.get(item_name, 0)
    
    if base_points <= 0:
        return 0.0
    
    # Apply divine multiplier
    final_points = base_points
    if divine:
        final_points = final_points * 2

    if quantity > 1 and final_points > 1:
        # For multiple quantities, each additional item is worth half points
        total_points = final_points + math.floor(final_points) / 2 * (quantity - 1)
    else:
        total_points = final_points * quantity
    
    return total_points


def create_loot_markdown_file(ppe_data: PPEData) -> str:
    """Create a temporary markdown file with the loot table and return the file path."""
    
    # Ensure temp directory exists
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create filename with PPE ID and class name
    safe_name = "".join(c for c in ppe_data.name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"loot_table_ppe_{ppe_data.id}_{safe_name}_{timestamp}.md"
    file_path = os.path.join(temp_dir, filename)
    
    # Build markdown content
    content = []
    
    # Title
    points_display = int(ppe_data.points) if ppe_data.points == int(ppe_data.points) else f"{ppe_data.points:.1f}"
    content.append(f"# Loot Table: {ppe_data.name} (PPE #{ppe_data.id})")
    content.append(f"Total Points: {points_display}\n")
    
    # Loot section
    if ppe_data.loot:
        content.append("## Loot Items")
        
        # Sort loot alphabetically by item name
        sorted_loot = sorted(ppe_data.loot, key=lambda loot: loot.item_name.lower())
        
        for loot in sorted_loot:
            # Calculate points for this item
            item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, loot.quantity)
            
            # Format points display
            points_display = int(item_points) if item_points == int(item_points) else f"{item_points:.1f}"
            
            # Build tags
            tags = []
            if loot.divine:
                tags.append("divine")
            if loot.shiny:
                tags.append("shiny")
            
            # Format the line
            line = f"{loot.item_name} × {loot.quantity} ({points_display} pts)"
            if tags:
                tags_display = ", ".join(tags)
                line += f" [{tags_display}]"
            
            content.append(line)
        
        content.append("")  # Empty line for spacing
    else:
        content.append("## Loot Items")
        content.append("*No loot recorded yet.*\n")
    
    # Bonuses section
    if ppe_data.bonuses:
        content.append("## Bonuses")
        
        # Sort bonuses alphabetically by name
        sorted_bonuses = sorted(ppe_data.bonuses, key=lambda bonus: bonus.name.lower())
        
        for bonus in sorted_bonuses:
            # Calculate total points for bonus
            total_bonus_points = bonus.points * bonus.quantity
            
            # Format points display
            points_display = int(total_bonus_points) if total_bonus_points == int(total_bonus_points) else f"{total_bonus_points:.1f}"
            if total_bonus_points > 0:
                points_display = f"+{points_display}"
            
            # Format the line
            line = f"{bonus.name} × {bonus.quantity} ({points_display} pts)"
            if bonus.repeatable:
                line += " [repeatable]"
            
            content.append(line)
        
        content.append("")  # Empty line for spacing
    
    # Summary
    total_loot_items = len(ppe_data.loot) if ppe_data.loot else 0
    total_bonus_items = len(ppe_data.bonuses) if ppe_data.bonuses else 0
    total_items = total_loot_items + total_bonus_items
    
    content.append("---")
    content.append(f"Summary: {total_items} total items ({total_loot_items} loot, {total_bonus_items} bonuses)")
    
    # Write to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(content))
    
    return file_path