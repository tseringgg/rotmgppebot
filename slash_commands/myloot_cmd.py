

import discord
import os

from utils.loot_table_md_builder import create_loot_markdown_file
from utils.player_records import get_active_ppe_of_user


async def command(interaction: discord.Interaction):
    try:
        active_ppe = await get_active_ppe_of_user(interaction)
        
        # Create temporary markdown file
        temp_file_path = create_loot_markdown_file(active_ppe)
        
        try:
            # Send the file as attachment
            await interaction.response.send_message(
                file=discord.File(temp_file_path), 
                ephemeral=True
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except (ValueError, KeyError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)