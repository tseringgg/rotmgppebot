import discord
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction, player: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Remove player from all teams
        team_name = await team_manager.remove_player_from_teams(interaction, player.id)
        
        if team_name:
            # Try to remove the team role from the player
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=team_name)
                if team_role:
                    await player.remove_roles(team_role)
            except discord.Forbidden:
                pass  # Silently ignore if we can't remove the role
            except Exception:
                pass  # Silently ignore any other errors
            
            return await interaction.response.send_message(
                f"✅ Removed `{player.display_name}` from team `{team_name}`."
            )
        else:
            return await interaction.response.send_message(
                f"⚠️ `{player.display_name}` is not on any team."
            )
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
