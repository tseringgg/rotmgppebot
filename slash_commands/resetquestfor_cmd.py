import discord
from discord import ui

from utils.player_records import load_player_records, save_player_records
from utils.quest_manager import refresh_player_quests


ACTION_RESET_COMPLETED_ITEMS = "action_reset_completed_items"
ACTION_RESET_COMPLETED_SKINS = "action_reset_completed_skins"
ACTION_CLEAR_ALL_INFO = "action_clear_all_info"


class ResetQuestSelectionView(ui.View):
    def __init__(
            self,
            *,
            admin_id: int,
            member: discord.Member,
            active_item_quests: list[str],
            active_skin_quests: list[str]
        ):
        super().__init__(timeout=120)
        self.admin_id = admin_id
        self.member = member
        self.active_item_quests = list(active_item_quests)
        self.active_skin_quests = list(active_skin_quests)
        self.selected_values: set[str] = set()
        self.omitted_active_options_count = 0

        active_options: list[discord.SelectOption] = []
        for idx, item_name in enumerate(self.active_item_quests):
            label = f"Item: {item_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            active_options.append(discord.SelectOption(label=label, value=f"item_idx::{idx}"))

        for idx, skin_name in enumerate(self.active_skin_quests):
            label = f"Skin: {skin_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            active_options.append(discord.SelectOption(label=label, value=f"skin_idx::{idx}"))

        bulk_options = [
            discord.SelectOption(label="Reset all completed items", value=ACTION_RESET_COMPLETED_ITEMS),
            discord.SelectOption(label="Reset all completed skins", value=ACTION_RESET_COMPLETED_SKINS),
            discord.SelectOption(label="Clear all quest information", value=ACTION_CLEAR_ALL_INFO),
        ]

        # Discord select menus support up to 25 options, so always reserve room
        # for the 3 required bulk actions.
        max_total_options = 25
        max_active_options = max_total_options - len(bulk_options)
        self.omitted_active_options_count = max(0, len(active_options) - max_active_options)
        self.section_select.options = active_options[:max_active_options] + bulk_options
        self.section_select.max_values = len(self.section_select.options)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message(
                "❌ Only the admin who started this action can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self.confirm_button.disabled = True
        self.cancel_button.disabled = True
        self.section_select.disabled = True

    @ui.select(
        placeholder="Choose quests/actions to reset...",
        min_values=0,
        max_values=1,
        options=[discord.SelectOption(label="Loading...", value="loading")],
    )
    async def section_select(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_values = set(select.values)
        if self.selected_values:
            pretty = ", ".join(sorted(self.selected_values))
            await interaction.response.send_message(f"Selected: {pretty}", ephemeral=True)
        else:
            await interaction.response.send_message("No sections selected yet.", ephemeral=True)

    @ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_values:
            return await interaction.response.send_message(
                "⚠️ Select at least one quest/action, or press Cancel.",
                ephemeral=True,
            )

        records = await load_player_records(interaction)
        key = self.member.id

        if key not in records or not records[key].is_member:
            self.stop()
            return await interaction.response.edit_message(
                content=f"❌ {self.member.display_name} is not part of the PPE contest.",
                view=None,
                embed=None,
            )

        player_data = records[key]
        quests = player_data.quests

        removed_current_items = []
        removed_current_skins = []
        reset_completed_items = False
        reset_completed_skins = False
        cleared_all_info = False

        if ACTION_CLEAR_ALL_INFO in self.selected_values:
            quests.current_items.clear()
            quests.current_skins.clear()
            quests.completed_items.clear()
            quests.completed_skins.clear()
            cleared_all_info = True
        else:
            if ACTION_RESET_COMPLETED_ITEMS in self.selected_values:
                quests.completed_items.clear()
                reset_completed_items = True
            if ACTION_RESET_COMPLETED_SKINS in self.selected_values:
                quests.completed_skins.clear()
                reset_completed_skins = True

            selected_item_indexes = {
                int(value.split("::", 1)[1])
                for value in self.selected_values
                if value.startswith("item_idx::")
            }
            selected_skin_indexes = {
                int(value.split("::", 1)[1])
                for value in self.selected_values
                if value.startswith("skin_idx::")
            }

            selected_item_quests = {
                self.active_item_quests[idx]
                for idx in selected_item_indexes
                if 0 <= idx < len(self.active_item_quests)
            }
            selected_skin_quests = {
                self.active_skin_quests[idx]
                for idx in selected_skin_indexes
                if 0 <= idx < len(self.active_skin_quests)
            }

            if selected_item_quests:
                before = list(quests.current_items)
                quests.current_items = [q for q in quests.current_items if q not in selected_item_quests]
                removed_current_items = [q for q in before if q in selected_item_quests]

            if selected_skin_quests:
                before = list(quests.current_skins)
                quests.current_skins = [q for q in quests.current_skins if q not in selected_skin_quests]
                removed_current_skins = [q for q in before if q in selected_skin_quests]

            # Refill active quest slots after removing active quests.
            if removed_current_items or removed_current_skins:
                refresh_player_quests(player_data)

        await save_player_records(interaction, records)

        summary_lines = [f"✅ Updated quest reset for {self.member.display_name}."]
        if removed_current_items:
            summary_lines.append(f"- Active item quests reset: {', '.join(removed_current_items)}")
        if removed_current_skins:
            summary_lines.append(f"- Active skin quests reset: {', '.join(removed_current_skins)}")
        if reset_completed_items:
            summary_lines.append("- Reset all completed item quests")
        if reset_completed_skins:
            summary_lines.append("- Reset all completed skin quests")
        if cleared_all_info:
            summary_lines.append("- Cleared all quest information")

        self.stop()
        await interaction.response.edit_message(
            content="\n".join(summary_lines + ["Use /viewquestsfor to verify the updated quest state."]),
            view=None,
            embed=None,
        )

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="Quest reset cancelled.",
            view=None,
            embed=None,
        )


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    try:
        records = await load_player_records(interaction)
        key = member.id

        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                f"❌ {member.display_name} is not part of the PPE contest.",
                ephemeral=True,
            )

        player_data = records[key]
        active_item_quests = list(player_data.quests.current_items)
        active_skin_quests = list(player_data.quests.current_skins)

        view = ResetQuestSelectionView(
            admin_id=interaction.user.id,
            member=member,
            active_item_quests=active_item_quests,
            active_skin_quests=active_skin_quests,
        )

        active_lines = []
        for item in active_item_quests:
            active_lines.append(f"- Item: {item}")
        for skin in active_skin_quests:
            active_lines.append(f"- Skin: {skin}")
        if not active_lines:
            active_lines = ["- None"]

        menu_note = ""
        if view.omitted_active_options_count > 0:
            menu_note = (
                "\nNote: "
                f"{view.omitted_active_options_count} active quest option(s) are hidden due to Discord's 25-option menu limit."
            )

        await interaction.response.send_message(
            (
                f"Choose quest sections to reset for {member.display_name}.\n"
                "Active quests:\n"
                + "\n".join(active_lines)
                + "\n\nAdditional options:\n"
                "- Reset all completed items\n"
                "- Reset all completed skins\n"
                "- Clear all quest information\n\n"
                "Select options below, then confirm or cancel."
                + menu_note
            ),
            view=view,
            ephemeral=True,
        )

    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
