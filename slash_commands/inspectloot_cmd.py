import discord
from utils.player_records import ensure_player_exists, load_player_records
from utils.embed_builders import build_loot_embed
from slash_commands.helpers.loot_table_message import LootTableMessage

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
        # Use LootTableMessage to handle embed display
        loot_message = LootTableMessage(
            interaction=interaction,
            message_type="markdown",
            ephemeral=True,
            embed_content=f"**Loot inspection for {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})**"
        )
        
        await loot_message.send_player_loot(target_ppe, user_id=user.id)
        
    except Exception as e:
        return await interaction.response.send_message(
            f"❌ Error building loot display: {str(e)}",
            ephemeral=True
        )