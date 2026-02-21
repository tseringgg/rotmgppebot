import discord
from utils.team_manager import team_manager
from utils.player_records import is_team_leader


async def command(interaction: discord.Interaction, old_name: str, new_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Check if user is a PPE Admin
        admin_role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
        is_admin = admin_role and admin_role in interaction.user.roles
        
        # Check if user is the team leader
        is_leader = await is_team_leader(interaction, interaction.user.id, old_name)
        
        if not is_admin and not is_leader:
            return await interaction.response.send_message(
                "🚫 You need to be a PPE Admin or the team leader to use this command."
            )
        
        # Update team name
        team = await team_manager.update_team_name(interaction, old_name, new_name)
        
        # Try to update the team role name
        try:
            old_role = discord.utils.get(interaction.guild.roles, name=old_name)
            if old_role:
                await old_role.edit(name=new_name, reason=f"PPE Team rename from {old_name} to {new_name}")
        except discord.Forbidden:
            return await interaction.response.send_message("❌ I don't have permission to manage roles. Move my bot role higher in the hierarchy.")
        except discord.HTTPException:
            # Role name might already exist, which is fine
            pass
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error updating team role: {str(e)}", ephemeral=True)
        
        return await interaction.response.send_message(
            f"✅ Team renamed from `{old_name}` to `{new_name}`."
        )
    except ValueError as e:
        return await interaction.response.send_message(str(e))
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
