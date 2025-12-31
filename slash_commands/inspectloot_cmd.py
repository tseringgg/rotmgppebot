import discord
from utils.player_records import ensure_player_exists, load_player_records
from utils.embed_builders import build_loot_embed

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
    
    try:
        # Build embed for the target PPE
        embed = await build_loot_embed(target_ppe, user_id=user.id)
        
        await interaction.response.send_message(
            f"**Loot inspection for {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})**",
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )
        
    except Exception as e:
        return await interaction.response.send_message(
            f"❌ Error building loot display: {str(e)}",
            ephemeral=True
        )