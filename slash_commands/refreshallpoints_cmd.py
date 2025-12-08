import discord
from utils.player_records import load_player_records, save_player_records
from utils.embed_builders import calculate_item_points

async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load player records
    records = await load_player_records(interaction)
    
    total_ppes_processed = 0
    total_corrections = 0
    correction_summary = []
    
    # Iterate through all players
    for player_key, player_data in records.items():
        if not player_data.ppes:
            continue
            
        # Process each PPE for this player
        for ppe in player_data.ppes:
            total_ppes_processed += 1
            
            # Store old points for comparison
            old_points = ppe.points
            
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
    
    # Create response message
    if total_corrections == 0:
        response = f"✅ **Refresh Complete!**\n\nProcessed **{total_ppes_processed} PPEs** - all point totals were already accurate!"
    else:
        correction_text = "\n".join(correction_summary[:10])  # Limit to first 10 to avoid message length issues
        if len(correction_summary) > 10:
            correction_text += f"\n... and {len(correction_summary) - 10} more corrections"
        
        response = (
            f"✅ **Refresh Complete!**\n\n"
            f"Processed **{total_ppes_processed} PPEs**\n"
            f"Made **{total_corrections} corrections**\n\n"
            f"**Corrections Made:**\n{correction_text}"
        )
    
    await interaction.response.send_message(response)