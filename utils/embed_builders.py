

import discord
import math
from dataclass import Loot, PPEData
from utils.calc_points import load_loot_points


def calculate_item_points(item_name: str, divine: bool, shiny: bool, quantity: int) -> float:
    """Calculate total points for an item based on its properties and quantity"""
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
    
    # Round down to nearest 0.5
    final_points = math.floor(final_points * 2) / 2
    
    # Multiply by quantity
    total_points = final_points * quantity
    
    return total_points


async def build_loot_embed(active_ppe: PPEData, recently_added: str = "") -> discord.Embed:
    loot_dict = active_ppe.loot
        
    loot_lines = []
    if not loot_dict:
        loot_lines.append("• _No loot recorded yet._")
    else:
        for loot in loot_dict:
            name_with_tags = loot.item_name
            if loot.divine:
                name_with_tags += " (divine)"
            if loot.shiny:
                name_with_tags += " (shiny)"
            
            # Calculate points for this item
            item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, loot.quantity)
            
            # Format points display
            if item_points == int(item_points):
                points_text = f"{int(item_points)}"
            else:
                points_text = f"{item_points:.1f}"
            
            if loot.item_name == recently_added:
                loot_lines.append(f"• **{name_with_tags} × {loot.quantity}** (+{points_text} pts) (+)")
            else:
                loot_lines.append(f"• *{name_with_tags} × {loot.quantity}* (+{points_text} pts)")

    embed = discord.Embed(
        title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
        description="\n".join(loot_lines),
        color=discord.Color.blue()
    )
    return embed