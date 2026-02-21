import discord
from utils.team_manager import team_manager
from utils.player_records import load_teams, save_teams


class ConfirmView(discord.ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.confirmed = False
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


async def command(interaction: discord.Interaction, team_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Ask for confirmation
        view = ConfirmView()
        await interaction.response.send_message(
            f"⚠️ **Are you sure you want to delete the team `{team_name}`?**\n"
            "This will remove the team and all its members will be removed from the team.",
            view=view,
            ephemeral=True
        )
        
        # Wait for user response
        await view.wait()
        
        if not view.confirmed:
            await interaction.followup.send("❌ Team deletion cancelled.", ephemeral=True)
            return
        
        # Load teams and records
        teams = await load_teams(interaction)
        
        # Find team (case-insensitive)
        actual_team_name = None
        for team_key in teams:
            if team_key.lower() == team_name.lower():
                actual_team_name = team_key
                break
        
        if not actual_team_name:
            return await interaction.followup.send(f"❌ Team `{team_name}` not found.", ephemeral=True)
        
        # Remove team from database
        team = teams.pop(actual_team_name)
        await save_teams(interaction, teams)
        
        # Remove team_name from all members
        from utils.player_records import load_player_records, save_player_records
        records = await load_player_records(interaction)
        members_removed = 0
        for member_id in team.members:
            if member_id in records:
                records[member_id].team_name = None
                members_removed += 1
        await save_player_records(interaction, records)
        
        # Try to delete the team role
        try:
            team_role = discord.utils.get(interaction.guild.roles, name=actual_team_name)
            if team_role:
                await team_role.delete(reason=f"PPE Team {actual_team_name} deleted")
        except discord.Forbidden:
            pass  # Silently ignore if we can't delete the role
        except Exception:
            pass  # Silently ignore any other errors
        
        await interaction.followup.send(
            f"✅ Team `{actual_team_name}` deleted successfully!\n"
            f"**Members removed from team:** {members_removed}",
            ephemeral=False
        )
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
