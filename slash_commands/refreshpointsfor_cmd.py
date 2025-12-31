import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import calculate_item_points, build_loot_embed

async def command(interaction: discord.Interaction, user: discord.Member, id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load player records
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user.id)
    player_data = records[key]
    
    # Check if target player has any PPEs
    if not player_data.ppes:
        return await interaction.response.send_message(
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
        return await interaction.response.send_message(
            f"❌ Could not find PPE #{id} for {user.display_name}.",
            ephemeral=True
        )
    
    # Store old points for comparison
    old_points = target_ppe.points
    
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
    if point_difference == 0:
        difference_text = "No correction needed - points were already accurate."
    elif point_difference > 0:
        difference_text = f"**+{point_difference:.1f} points** (points were too low)"
    else:
        difference_text = f"**{point_difference:.1f} points** (points were too high)"
    
    # Build embed
    embed = await build_loot_embed(target_ppe, user_id=user.id)
    
    await interaction.response.send_message(
        f"✅ Refreshed points for {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})!\n\n"
        f"**Old Total:** {old_points:.1f} points\n"
        f"**New Total:** {corrected_total:.1f} points, From Loot: {total_loot_points:.1f} points, From Bonuses: {total_bonus_points:.1f} points\n"
        f"**Correction:** {difference_text}",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )