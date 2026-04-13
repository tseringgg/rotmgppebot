import discord

from utils.player_records import ensure_player_exists, load_player_records
from utils.loot_data import LOOT
from utils.loot_ops import (
    format_ppe_remove_message,
    remove_ppe_loot,
    send_ppe_markdown_followup,
    validate_loot_input,
)

async def command(interaction: discord.Interaction, user: discord.Member, id: int, item_name: str, rarity: str, shiny: bool = False):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        validate_loot_input(item_name, shiny=shiny, known_items=LOOT)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
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
        rarity_normalized = rarity.lower().strip()

        result = await remove_ppe_loot(
            interaction,
            user=user,
            ppe_id=id,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity_normalized,
        )
        
        await interaction.response.send_message(format_ppe_remove_message(result))

        await send_ppe_markdown_followup(interaction, ppe=result.ppe, ephemeral=True)
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)