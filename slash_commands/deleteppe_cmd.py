import discord

from utils.player_manager import player_manager


async def command(interaction: discord.Interaction, member: discord.Member, ppe_id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        await player_manager.delete_ppe(interaction, member.id, ppe_id)
        await interaction.response.send_message(f"✅ PPE #{ppe_id} of {member.display_name} has been deleted.")
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)