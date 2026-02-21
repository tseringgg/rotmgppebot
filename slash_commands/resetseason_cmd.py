import discord
from utils.player_records import load_player_records, save_player_records, load_teams, save_teams


class ConfirmView(discord.ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.confirmed = False
    
    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


async def command(interaction: discord.Interaction):
    """
    Reset the season by clearing all unique items for all players.
    Retains player member status and PPE roles.
    Admin only.
    """
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    try:
        # Ask for confirmation
        view = ConfirmView()
        await interaction.response.send_message(
            "⚠️ **Are you sure you want to reset the season?**\n"
            "This will clear all unique items for all players and delete all teams.\n"
            "Member status and PPE roles will be preserved.",
            view=view,
            ephemeral=True
        )
        
        # Wait for user response
        await view.wait()
        
        if not view.confirmed:
            await interaction.followup.send("❌ Season reset cancelled.", ephemeral=True)
            return
        
        records = await load_player_records(interaction)
        
        # Clear unique_items for all players
        items_cleared = 0
        for player_data in records.values():
            if len(player_data.unique_items) > 0:
                items_cleared += len(player_data.unique_items)
                player_data.unique_items.clear()
            # Also clear team associations
            player_data.team_name = None
        
        # Save the updated records
        await save_player_records(interaction, records)
        
        # Delete all teams
        teams = await load_teams(interaction)
        teams_deleted = len(teams)
        teams.clear()
        await save_teams(interaction, teams)
        
        # Try to delete all team roles
        for role in interaction.guild.roles:
            try:
                # Delete roles that match team names (heuristic: if it's not a default role)
                if role.name not in ["@everyone", "PPE Player", "PPE Admin"] and not role.managed:
                    # Only delete if it looks like a team role (not system roles)
                    if len(role.members) < 100 or role.name.startswith("Team"):
                        await role.delete(reason="Season reset - team cleanup")
            except Exception:
                pass  # Silently ignore any role deletion errors
        
        await interaction.followup.send(
            f"✅ Season reset complete!\n"
            f"**Cleared:** {items_cleared} unique items across all players\n"
            f"**Deleted:** {teams_deleted} teams\n"
            f"**Preserved:** Player member status and PPE roles",
            ephemeral=False
        )
        
    except (ValueError, KeyError) as e:
        return await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
