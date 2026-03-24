

import discord
import math
from typing import List
from dataclass import Loot, PPEData
from utils.calc_points import load_loot_points
from utils.pagination import chunk_lines_to_pages, LootPaginationView
from utils.player_records import get_active_ppe_of_user


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


# async def build_loot_embed(active_ppe: PPEData, recently_added: str = "") -> discord.Embed:
#     loot_dict = active_ppe.loot
        
#     loot_lines = []
#     if not loot_dict:
#         loot_lines.append("• _No loot recorded yet._")
#     else:
#         for loot in loot_dict:
#             name_with_tags = loot.item_name
#             if loot.divine:
#                 name_with_tags += " (divine)"
#             if loot.shiny:
#                 name_with_tags += " (shiny)"
            
#             # Calculate points for this item
#             item_points = calculate_item_points(loot.item_name, loot.divine, loot.shiny, loot.quantity)
            
#             # Format points display
#             if item_points == int(item_points):
#                 points_text = f"{int(item_points)}"
#             else:
#                 points_text = f"{item_points:.1f}"
            
#             if loot.item_name == recently_added:
#                 loot_lines.append(f"• **{name_with_tags} × {loot.quantity}** (+{points_text} pts) (+)")
#             else:
#                 loot_lines.append(f"• *{name_with_tags} × {loot.quantity}* (+{points_text} pts)")

#     # Add bonuses section
#     bonus_lines = []
#     if active_ppe.bonuses:
#         bonus_lines.append("\n** Bonuses:**")
#         for bonus in active_ppe.bonuses:
#             # Format points display
#             if bonus.points == int(bonus.points):
#                 points_text = f"{int(bonus.points * bonus.quantity)}"
#             else:
#                 points_text = f"{bonus.points * bonus.quantity:.1f}"

#             if bonus.points >= 0:
#                 points_text = f"+{points_text}"
            
#             # Add quantity display if greater than 1
#             quantity_text = f" × {bonus.quantity}" if bonus.quantity > 1 else ""
#             repeatable_text = " (repeatable)" if bonus.repeatable else ""
            
#             if bonus.name == recently_added:
#                 bonus_lines.append(f"• **{bonus.name}{quantity_text} ({points_text} pts){repeatable_text}** (+)")
#             else:
#                 bonus_lines.append(f"• *{bonus.name}{quantity_text} ({points_text} pts){repeatable_text}*")

#     # Combine loot and bonuses
#     all_lines = loot_lines + bonus_lines

#     embed = discord.Embed(
#         title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
#         description="\n".join(all_lines),
#         color=discord.Color.blue()
#     )
#     return embed
async def build_loot_embed(active_ppe: PPEData, user_id: int, recently_added: str = "") -> LootPaginationView:
    """Build and send paginated loot embeds for the user's active PPE."""
    embeds = build_loot_embeds(active_ppe, recently_added="")  # or pass recently_added item
        
    # if len(embeds) == 1:
    #     # Single page - send normally without pagination
    #     await interaction.response.send_message(embed=embeds[0])
    # else:
    # Multiple pages - send with pagination view
    view = LootPaginationView(embeds, user_id)
    return view

def build_loot_embeds(active_ppe: PPEData, recently_added: str = "") -> List[discord.Embed]:
    """Build paginated loot embeds, splitting content to stay within Discord limits."""
    loot_dict = active_ppe.loot
        
    loot_lines = []
    if not loot_dict:
        loot_lines.append("• _No loot recorded yet._")
    else:
        # Sort loot alphabetically by item name
        sorted_loot = sorted(loot_dict, key=lambda loot: loot.item_name.lower())
        for loot in sorted_loot:
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

    # Add bonuses section
    bonus_lines = []
    if active_ppe.bonuses:
        bonus_lines.append("\n** Bonuses:**")
        # Sort bonuses alphabetically by name
        sorted_bonuses = sorted(active_ppe.bonuses, key=lambda bonus: bonus.name.lower())
        for bonus in sorted_bonuses:
            # Format points display
            if bonus.points == int(bonus.points):
                points_text = f"{int(bonus.points * bonus.quantity)}"
            else:
                points_text = f"{bonus.points * bonus.quantity:.1f}"

            if bonus.points >= 0:
                points_text = f"+{points_text}"
            
            # Add quantity display if greater than 1
            quantity_text = f" × {bonus.quantity}" if bonus.quantity > 1 else ""
            repeatable_text = " (repeatable)" if bonus.repeatable else ""
            
            if bonus.name == recently_added:
                bonus_lines.append(f"• **{bonus.name}{quantity_text} ({points_text} pts){repeatable_text}** (+)")
            else:
                bonus_lines.append(f"• *{bonus.name}{quantity_text} ({points_text} pts){repeatable_text}*")

    # Combine loot and bonuses
    all_lines = loot_lines + bonus_lines
    
    # Calculate total items count
    total_loot_items = len(loot_dict) if loot_dict else 0
    total_bonus_items = len(active_ppe.bonuses) if active_ppe.bonuses else 0
    total_items = total_loot_items + total_bonus_items
    
    # Split into pages (target 3800 chars to be safe)
    pages = chunk_lines_to_pages(all_lines, 1000)
    
    # Build embeds for each page
    embeds = []
    for i, page_lines in enumerate(pages):
        embed = discord.Embed(
            title=f"Loot for your {active_ppe.name} (PPE #{active_ppe.id}) ({int(active_ppe.points) if active_ppe.points == int(active_ppe.points) else f'{active_ppe.points:.1f}'} points)",
            description="\n".join(page_lines),
            color=discord.Color.blue()
        )
        
        # Add footer with page info
        footer_text = f"Page {i + 1}/{len(pages)} • Total items: {total_items}"
        if hasattr(active_ppe, 'points') and active_ppe.points is not None and active_ppe.points > 0:
            if active_ppe.points == int(active_ppe.points):
                footer_text += f" • Total points: {int(active_ppe.points)}"
            else:
                footer_text += f" • Total points: {active_ppe.points:.1f}"
        embed.set_footer(text=footer_text)
        
        embeds.append(embed)
    
    return embeds
