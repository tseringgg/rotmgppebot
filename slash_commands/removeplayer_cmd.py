

import discord

from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.player_manager import player_manager
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    role = discord.utils.get(interaction.guild.roles, name="PPE Player")
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")
    
    try:
        # Remove player from team first (this removes them from team.members and team_name)
        team_name = await team_manager.remove_player_from_teams(interaction, member.id)
        
        # Remove all PPE characters and associated data
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, member.id)
        
        if key in records:
            player_data = records[key]
            # Clear all PPE data
            player_data.ppes.clear()
            player_data.active_ppe = None
            player_data.unique_items.clear()
            player_data.is_member = False
        
        await save_player_records(interaction, records)
        
        # Remove the PPE Player role if they have it
        if role in member.roles:
            await member.remove_roles(role)
        
        # Remove the team role if they were on a team
        if team_name:
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=team_name)
                if team_role and team_role in member.roles:
                    await member.remove_roles(team_role)
            except discord.Forbidden:
                pass  # Silently ignore if we can't remove the role
            except Exception:
                pass  # Silently ignore any other errors
        
        return await interaction.response.send_message(f"✅ Removed `{member.display_name}` from the PPE contest. All PPE characters and data have been deleted.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)