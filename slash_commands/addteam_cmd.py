import discord
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction, team_name: str, team_leader: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Create the team
        team = await team_manager.add_team(interaction, team_name, team_leader.id)
        
        # Create a role for the team
        try:
            team_role = await interaction.guild.create_role(
                name=team_name,
                reason=f"PPE Team role for {team_name}"
            )
            await team_leader.add_roles(team_role)
        except discord.Forbidden:
            await team_manager.execute_transaction(
                interaction,
                lambda teams, records, i: teams.pop(team_name, None)
            )
            return await interaction.response.send_message("❌ I don't have permission to create roles. Move my bot role higher in the hierarchy.")
        except Exception as e:
            await team_manager.execute_transaction(
                interaction,
                lambda teams, records, i: teams.pop(team_name, None)
            )
            return await interaction.response.send_message(f"❌ Error creating team role: {str(e)}", ephemeral=True)
        
        return await interaction.response.send_message(
            f"✅ Team `{team.name}` created successfully with `{team_leader.display_name}` as leader."
        )
    except ValueError as e:
        return await interaction.response.send_message(str(e))
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
