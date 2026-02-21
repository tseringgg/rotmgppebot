import discord
from utils.team_manager import team_manager
from utils.player_records import load_teams, is_team_leader


async def command(interaction: discord.Interaction, player: discord.Member, team_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Check if user is a PPE Admin
        admin_role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
        is_admin = admin_role and admin_role in interaction.user.roles
        
        # Check if user is the team leader
        is_leader = await is_team_leader(interaction, interaction.user.id, team_name)
        
        if not is_admin and not is_leader:
            return await interaction.response.send_message(
                "🚫 You need to be a PPE Admin or the team leader to use this command."
            )
        
        # Add player to team
        team = await team_manager.add_player_to_team(interaction, player.id, team_name)
        
        # Get the team role and add it to the player
        try:
            team_role = discord.utils.get(interaction.guild.roles, name=team.name)
            if team_role:
                await player.add_roles(team_role)
            else:
                # Try to create the role if it doesn't exist
                team_role = await interaction.guild.create_role(
                    name=team.name,
                    reason=f"PPE Team role for {team.name}"
                )
                await player.add_roles(team_role)
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I don't have permission to manage roles. Move my bot role higher in the hierarchy.")
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error managing team role: {str(e)}", ephemeral=True)
        
        return await interaction.response.send_message(
            f"✅ Added `{player.display_name}` to team `{team.name}`."
        )
    except ValueError as e:
        return await interaction.response.send_message(str(e))
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
