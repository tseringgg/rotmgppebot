

import discord

from utils.player_manager import player_manager


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")
    
    if role in member.roles:
        try:
            await player_manager.add_player_to_contest(interaction, member.id)
            return await interaction.response.send_message(f"⚠️ `{member.display_name}` already has the `PPE Player` role.")
        except Exception as e:
            return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        await member.add_roles(role)
        await player_manager.add_player_to_contest(interaction, member.id)
        return await interaction.response.send_message(f"✅ Added `{member.display_name}` to the PPE contest. They can now use PPE commands.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)