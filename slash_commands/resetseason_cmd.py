import discord
from utils.player_records import load_player_records, save_player_records


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
            "This will clear all unique items for all players.\n"
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
        
        # Save the updated records
        await save_player_records(interaction, records)
        
        await interaction.followup.send(
            f"✅ Season reset complete!\n"
            f"**Cleared:** {items_cleared} unique items across all players\n"
            f"**Preserved:** Player member status and PPE roles",
            ephemeral=False
        )
        
    except (ValueError, KeyError) as e:
        return await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
