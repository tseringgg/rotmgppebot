

import discord

from utils.player_manager import player_manager


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        await player_manager.delete_all_ppes(interaction, member.id)
        await interaction.response.send_message(f"✅ All of {member.display_name}'s PPEs have been deleted.")
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)