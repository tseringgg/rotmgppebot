import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.bonus_data import load_bonuses
from utils.embed_builders import build_loot_embed

async def command(interaction: discord.Interaction, bonus_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load player records
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    
    # Check if player has an active PPE
    if player_data.active_ppe is None:
        return await interaction.response.send_message(
            "❌ You don't have an active PPE. Create one first with `/newppe`.",
            ephemeral=True
        )
    
    # Find the active PPE
    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break
    
    if not active_ppe:
        return await interaction.response.send_message(
            "❌ Could not find your active PPE.",
            ephemeral=True
        )
    
    # Find the bonus to remove
    bonus_to_remove = None
    
    for bonus in active_ppe.bonuses:
        if bonus.name.lower() == bonus_name.lower():
            bonus_to_remove = bonus
            break
    
    if bonus_to_remove is None:
        return await interaction.response.send_message(
            f"❌ You don't have the bonus `{bonus_name}` in your active PPE.",
            ephemeral=True
        )
    
    # Handle quantity logic
    if bonus_to_remove.quantity > 1:
        # Decrement quantity
        bonus_to_remove.quantity -= 1
        active_ppe.points -= bonus_to_remove.points
        quantity_text = f" (remaining quantity: {bonus_to_remove.quantity})"
        removed_points = bonus_to_remove.points
        removed_name = bonus_to_remove.name
    else:
        # Remove bonus completely
        active_ppe.bonuses.remove(bonus_to_remove)
        active_ppe.points -= bonus_to_remove.points
        quantity_text = ""
        removed_points = bonus_to_remove.points
        removed_name = bonus_to_remove.name
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Create response message and embed
    embed = await build_loot_embed(active_ppe, removed_name)
    
    await interaction.response.send_message(
        f"✅ Removed bonus `{removed_name}` from PPE #{active_ppe.id} ({active_ppe.name})!{quantity_text}\n"
        f"**-{removed_points} points**\n"
        f"Your PPE now has **{active_ppe.points} total points**.",
        embed=embed
    )