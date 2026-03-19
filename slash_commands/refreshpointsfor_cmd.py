import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import calculate_item_points, build_loot_embed
from utils.calc_points import load_loot_points
from utils.pagination import chunk_lines_to_pages

async def command(interaction: discord.Interaction, user: discord.Member, id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    # Keep the interaction alive in case recalculation or embed building takes time.
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    # Load player records and loot data
    records = await load_player_records(interaction)
    loot_points = load_loot_points()
    key = ensure_player_exists(records, user.id)
    player_data = records[key]
    
    # Check if target player has any PPEs
    if not player_data.ppes:
        return await interaction.followup.send(
            f"❌ {user.display_name} doesn't have any PPEs.",
            ephemeral=True
        )
    
    # Find the specific PPE by ID
    target_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == id:
            target_ppe = ppe
            break
    
    if not target_ppe:
        return await interaction.followup.send(
            f"❌ Could not find PPE #{id} for {user.display_name}.",
            ephemeral=True
        )
    
    # Store old points for comparison
    old_points = target_ppe.points
    
    # Validate and remove invalid items
    # Track invalid removals as: {item_label: {"total_quantity": int, "characters": [str]}}
    removed_items_by_item = {}
    valid_loot = []
    for loot_item in target_ppe.loot:
        # Check if item exists in loot_points
        if loot_item.shiny:
            lookup_name = f"{loot_item.item_name} (shiny)"
        else:
            lookup_name = loot_item.item_name
        
        if lookup_name not in loot_points:
            # Item is invalid, flag it for removal
            item_label = f"{loot_item.item_name}{' (shiny)' if loot_item.shiny else ''}{' (divine)' if loot_item.divine else ''}"
            item_summary = removed_items_by_item.setdefault(
                item_label,
                {"total_quantity": 0, "characters": []}
            )

            item_summary["total_quantity"] += loot_item.quantity
            item_summary["characters"].append(
                f"PPE #{target_ppe.id} ({target_ppe.name}) x{loot_item.quantity}"
            )
        else:
            valid_loot.append(loot_item)
    
    # Update the loot list with only valid items
    target_ppe.loot = valid_loot
    
    # Recalculate points from loot
    total_loot_points = 0.0
    for loot_item in target_ppe.loot:
        item_points = calculate_item_points(
            loot_item.item_name, 
            loot_item.divine, 
            loot_item.shiny, 
            loot_item.quantity
        )
        total_loot_points += item_points
    
    # Recalculate points from bonuses
    total_bonus_points = 0.0
    for bonus in target_ppe.bonuses:
        bonus_points = bonus.points * bonus.quantity
        total_bonus_points += bonus_points
    
    # Set the corrected total
    corrected_total = total_loot_points + total_bonus_points
    target_ppe.points = corrected_total
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Calculate the difference
    point_difference = corrected_total - old_points
    
    # Create response message
    if point_difference == 0 and not removed_items_by_item:
        difference_text = "No correction needed - points were already accurate."
    elif point_difference > 0:
        difference_text = f"**+{point_difference:.1f} points** (points were too low)"
    else:
        difference_text = f"**{point_difference:.1f} points** (points were too high)"
    
    # Build base response lines
    response_lines = []
    response_lines.append(f"✅ Refreshed points for {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})!")
    response_lines.append("")
    response_lines.append(f"**Old Total:** {old_points:.1f} points")
    response_lines.append(f"**New Total:** {corrected_total:.1f} points")
    response_lines.append(f"**From Loot:** {total_loot_points:.1f} points")
    response_lines.append(f"**From Bonuses:** {total_bonus_points:.1f} points")
    response_lines.append(f"**Correction:** {difference_text}")
    
    if removed_items_by_item:
        response_lines.append("")
        total_removed_quantity = sum(item_data["total_quantity"] for item_data in removed_items_by_item.values())
        response_lines.append(f"**Removed Invalid Items ({total_removed_quantity} total):**")

        for item_label in sorted(removed_items_by_item.keys()):
            item_data = removed_items_by_item[item_label]
            character_breakdown = "; ".join(item_data["characters"])
            response_lines.append(
                f"• **{item_label}** x{item_data['total_quantity']} from: {character_breakdown}"
            )
    
    # Split into pages if necessary
    pages = chunk_lines_to_pages(response_lines, 1900)
    
    # Build embed
    embed = await build_loot_embed(target_ppe, user_id=user.id)
    
    if len(pages) == 1:
        await interaction.followup.send(
            "\n".join(pages[0]),
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )
    else:
        # Send first page with embed
        first_message = "\n".join(pages[0]) + f"\n\n*[Part 1 of {len(pages)}]*"
        await interaction.followup.send(
            first_message,
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )
        
        # Send additional pages without embed
        for i, page in enumerate(pages[1:], start=2):
            page_text = "\n".join(page) + f"\n\n*[Part {i} of {len(pages)}]*"
            await interaction.followup.send(page_text, ephemeral=True)