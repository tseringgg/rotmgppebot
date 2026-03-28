import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import build_loot_embed
from utils.guild_config import load_guild_config
from utils.points_service import recompute_ppe_points

async def command(interaction: discord.Interaction, user: discord.Member, id: int, bonus_name: str):
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
    
    # Find the bonus to remove
    bonus_to_remove = None
    
    for bonus in target_ppe.bonuses:
        if bonus.name.lower() == bonus_name.lower():
            bonus_to_remove = bonus
            break
    
    if bonus_to_remove is None:
        return await interaction.response.send_message(
            f"❌ PPE #{id} doesn't have the bonus `{bonus_name}`.",
            ephemeral=True
        )
    
    # Handle quantity logic
    if bonus_to_remove.quantity > 1:
        # Decrement quantity
        bonus_to_remove.quantity -= 1
        quantity_text = f" (remaining quantity: {bonus_to_remove.quantity})"
        removed_points = bonus_to_remove.points
        removed_name = bonus_to_remove.name
    else:
        # Remove bonus completely
        target_ppe.bonuses.remove(bonus_to_remove)
        quantity_text = ""
        removed_points = bonus_to_remove.points
        removed_name = bonus_to_remove.name

    guild_config = await load_guild_config(interaction)
    recompute_ppe_points(target_ppe, guild_config)
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Create response message and embed
    embed = await build_loot_embed(target_ppe, user_id=user.id, recently_added=removed_name)
    
    await interaction.response.send_message(
        f"✅ Removed bonus `{removed_name}` from {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})!{quantity_text}\n"
        f"**-{removed_points} points**\n"
    )
    await interaction.followup.send(
        f"Their PPE now has **{target_ppe.points} total points**.",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )