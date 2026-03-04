import discord
from utils.player_records import load_player_records, save_player_records
from utils.embed_builders import calculate_item_points
from utils.calc_points import load_loot_points
from utils.pagination import chunk_lines_to_pages

async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load player records and loot data
    records = await load_player_records(interaction)
    loot_points = load_loot_points()
    
    total_ppes_processed = 0
    total_corrections = 0
    correction_summary = []
    removed_items_summary = []
    
    # Iterate through all players
    for player_key, player_data in records.items():
        if not player_data.ppes:
            continue
            
        # Process each PPE for this player
        for ppe in player_data.ppes:
            total_ppes_processed += 1
            
            # Store old points for comparison
            old_points = ppe.points
            
            # Validate and remove invalid items
            valid_loot = []
            for loot_item in ppe.loot:
                # Check if item exists in loot_points
                if loot_item.shiny:
                    lookup_name = f"{loot_item.item_name} (shiny)"
                else:
                    lookup_name = loot_item.item_name
                
                if lookup_name not in loot_points:
                    # Item is invalid, flag it for removal
                    try:
                        member = interaction.guild.get_member(int(player_key))
                        player_name = member.display_name if member else f"User {player_key}"
                    except:
                        player_name = f"User {player_key}"
                    
                    removed_items_summary.append(
                        f"• **{player_name}** - PPE #{ppe.id} ({ppe.name}): "
                        f"Removed **{loot_item.item_name}{' (shiny)' if loot_item.shiny else ''}{' (divine)' if loot_item.divine else ''}** (x{loot_item.quantity})"
                    )
                else:
                    valid_loot.append(loot_item)
            
            # Update the loot list with only valid items
            ppe.loot = valid_loot
            
            # Recalculate points from loot
            total_loot_points = 0.0
            for loot_item in ppe.loot:
                item_points = calculate_item_points(
                    loot_item.item_name, 
                    loot_item.divine, 
                    loot_item.shiny, 
                    loot_item.quantity
                )
                total_loot_points += item_points
            
            # Recalculate points from bonuses
            total_bonus_points = 0.0
            for bonus in ppe.bonuses:
                bonus_points = bonus.points * bonus.quantity
                total_bonus_points += bonus_points
            
            # Set the corrected total
            corrected_total = total_loot_points + total_bonus_points
            ppe.points = corrected_total
            
            # Track corrections
            point_difference = corrected_total - old_points
            if abs(point_difference) > 0.01:  # Only count meaningful differences
                total_corrections += 1
                # Try to get player name from Discord
                try:
                    member = interaction.guild.get_member(int(player_key))
                    player_name = member.display_name if member else f"User {player_key}"
                except:
                    player_name = f"User {player_key}"
                
                correction_summary.append(
                    f"• {player_name} - PPE #{ppe.id} ({ppe.name}): "
                    f"{old_points:.1f} → {corrected_total:.1f} "
                    f"({point_difference:+.1f})"
                )
    
    # Save all records
    await save_player_records(interaction=interaction, records=records)
    
    # Build response message with pagination
    response_lines = [f"✅ **Refresh Complete!**", ""]
    response_lines.append(f"Processed **{total_ppes_processed} PPEs**")
    response_lines.append(f"Made **{total_corrections} corrections**")
    
    if removed_items_summary:
        response_lines.append("")
        response_lines.append(f"**Removed Invalid Items ({len(removed_items_summary)}):**")
        response_lines.extend(removed_items_summary)
    
    if correction_summary:
        response_lines.append("")
        response_lines.append(f"**Point Corrections Made:**")
        response_lines.extend(correction_summary)
    
    # Split into pages if necessary
    pages = chunk_lines_to_pages(response_lines, 1900)
    
    if len(pages) == 1:
        await interaction.response.send_message("\n".join(pages[0]))
    else:
        # Send first page with footer, then additional pages
        first_message = "\n".join(pages[0]) + f"\n\n*[Part 1 of {len(pages)}]*"
        await interaction.response.send_message(first_message)
        
        for i, page in enumerate(pages[1:], start=2):
            page_text = "\n".join(page) + f"\n\n*[Part {i} of {len(pages)}]*"
            await interaction.followup.send(page_text)