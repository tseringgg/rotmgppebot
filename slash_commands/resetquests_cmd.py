import discord

from utils.player_records import load_player_records, save_player_records


class ConfirmResetAllQuestsView(discord.ui.View):
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
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    try:
        view = ConfirmResetAllQuestsView()
        await interaction.response.send_message(
            "⚠️ **Are you sure you want to reset ALL quest data?**\n"
            "This will clear current and completed regular, shiny, and skin quests for all players.",
            view=view,
            ephemeral=True,
        )

        await view.wait()
        if not view.confirmed:
            return await interaction.followup.send("❌ Reset all quests cancelled.", ephemeral=True)

        records = await load_player_records(interaction)

        players_updated = 0
        quest_entries_cleared = 0

        for player_data in records.values():
            player_entries = (
                len(player_data.quests.current_items)
                + len(player_data.quests.current_shinies)
                + len(player_data.quests.current_skins)
                + len(player_data.quests.completed_items)
                + len(player_data.quests.completed_shinies)
                + len(player_data.quests.completed_skins)
            )

            if player_entries == 0:
                continue

            quest_entries_cleared += player_entries
            players_updated += 1

            player_data.quests.current_items.clear()
            player_data.quests.current_shinies.clear()
            player_data.quests.current_skins.clear()
            player_data.quests.completed_items.clear()
            player_data.quests.completed_shinies.clear()
            player_data.quests.completed_skins.clear()

        if players_updated == 0:
            return await interaction.followup.send(
                "ℹ️ No quest data found to reset.",
                ephemeral=True,
            )

        await save_player_records(interaction, records)

        return await interaction.followup.send(
            f"✅ Reset quests for {players_updated} player(s). Cleared {quest_entries_cleared} quest entries.\n"
            "Players will get fresh quests the next time they run /myquests."
        )
    except (ValueError, KeyError, LookupError) as e:
        if interaction.response.is_done():
            return await interaction.followup.send(str(e), ephemeral=True)
        return await interaction.response.send_message(str(e), ephemeral=True)
