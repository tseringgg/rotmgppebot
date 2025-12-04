

import discord

from utils.player_manager import player_manager


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")
    
    if role not in member.roles:
        try:
            await player_manager.remove_player_from_contest(interaction, member.id)
            return await interaction.response.send_message(f"⚠️ `{member.display_name}` already does not have the `PPE Player` role.")
        except Exception as e:
            return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        await member.remove_roles(role)
        await player_manager.remove_player_from_contest(interaction, member.id)
        return await interaction.response.send_message(f"✅ Removed `{member.display_name}` from the PPE contest. They will no longer show on leaderboards or be able to use PPE commands.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)