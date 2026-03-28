

import discord

from utils.player_records import get_active_ppe_of_user
from utils.helpers.loot_table_message import LootTableMessage


async def command(interaction: discord.Interaction):
    """
    Show all loot for user's active PPE as a downloadable markdown file.
    Now using the centralized LootTableMessage class.
    """
    try:
        active_ppe = await get_active_ppe_of_user(interaction)
        
        # Create and configure loot table message
        loot_message = LootTableMessage(
            interaction=interaction,
            message_type="markdown",
            ephemeral=True
        )
        
        # Send the loot table
        await loot_message.send_player_loot(active_ppe)
        
    except (ValueError, KeyError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)