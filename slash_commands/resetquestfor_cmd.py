import discord
from discord import ui

from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.quest_manager import refresh_player_quests
from utils.guild_config import get_quest_targets, load_guild_config


ACTION_RESET_COMPLETED_ITEMS = "action_reset_completed_items"
ACTION_RESET_COMPLETED_SHINIES = "action_reset_completed_shinies"
ACTION_RESET_COMPLETED_SKINS = "action_reset_completed_skins"
ACTION_CLEAR_ALL_INFO = "action_clear_all_info"
ACTION_RESET_RESETS_TO_DEFAULT = "action_reset_resets_to_default"


def _coerce_resets_remaining(player_data, default_reset_limit: int) -> int:
    value = player_data.quest_resets_remaining
    if value is None:
        return max(0, default_reset_limit)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, default_reset_limit)


def _build_active_lines(
    active_item_quests: list[str],
    active_shiny_quests: list[str],
    active_skin_quests: list[str],
) -> list[str]:
    active_lines = []
    for item in active_item_quests:
        active_lines.append(f"- Item: {item}")
    for shiny in active_shiny_quests:
        active_lines.append(f"- Shiny: {shiny}")
    for skin in active_skin_quests:
        active_lines.append(f"- Skin: {skin}")
    return active_lines or ["- None"]


class ResetQuestSelectionView(ui.View):
    def __init__(
        self,
        *,
        actor_id: int,
        member: discord.Member,
        active_item_quests: list[str],
        active_shiny_quests: list[str],
        active_skin_quests: list[str],
        default_reset_limit: int,
        consume_reset_on_confirm: bool,
        include_reset_counter_option: bool,
    ):
        super().__init__(timeout=120)
        self.actor_id = actor_id
        self.member = member
        self.active_item_quests = list(active_item_quests)
        self.active_shiny_quests = list(active_shiny_quests)
        self.active_skin_quests = list(active_skin_quests)
        self.default_reset_limit = max(0, int(default_reset_limit))
        self.consume_reset_on_confirm = consume_reset_on_confirm
        self.include_reset_counter_option = include_reset_counter_option
        self.selected_values: set[str] = set()
        self.omitted_active_options_count = 0

        active_options: list[discord.SelectOption] = []
        for idx, item_name in enumerate(self.active_item_quests):
            label = f"Item: {item_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            active_options.append(discord.SelectOption(label=label, value=f"item_idx::{idx}"))

        for idx, shiny_name in enumerate(self.active_shiny_quests):
            label = f"Shiny: {shiny_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            active_options.append(discord.SelectOption(label=label, value=f"shiny_idx::{idx}"))

        for idx, skin_name in enumerate(self.active_skin_quests):
            label = f"Skin: {skin_name}"
            if len(label) > 100:
                label = label[:97] + "..."
            active_options.append(discord.SelectOption(label=label, value=f"skin_idx::{idx}"))

        bulk_options = [
            discord.SelectOption(label="Reset all completed items", value=ACTION_RESET_COMPLETED_ITEMS),
            discord.SelectOption(label="Reset all completed shinies", value=ACTION_RESET_COMPLETED_SHINIES),
            discord.SelectOption(label="Reset all completed skins", value=ACTION_RESET_COMPLETED_SKINS),
            discord.SelectOption(label="Clear all quest information", value=ACTION_CLEAR_ALL_INFO),
        ]

        if self.include_reset_counter_option:
            bulk_options.append(
                discord.SelectOption(
                    label="Reset quest reset attempts to default",
                    value=ACTION_RESET_RESETS_TO_DEFAULT,
                )
            )

        max_total_options = 25
        max_active_options = max_total_options - len(bulk_options)
        self.omitted_active_options_count = max(0, len(active_options) - max_active_options)
        self.section_select.options = active_options[:max_active_options] + bulk_options
        self.section_select.max_values = len(self.section_select.options)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "❌ Only the user who started this action can use these controls.",
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

        current_resets_remaining = _coerce_resets_remaining(player_data, self.default_reset_limit)
        if player_data.quest_resets_remaining != current_resets_remaining:
            player_data.quest_resets_remaining = current_resets_remaining

        if self.consume_reset_on_confirm and current_resets_remaining <= 0:
            self.stop()
            await save_player_records(interaction, records)
            return await interaction.response.edit_message(
                content="❌ You have no quest resets left.",
                view=None,
                embed=None,
            )

        removed_current_items = []
        removed_current_shinies = []
        removed_current_skins = []
        reset_completed_items = False
        reset_completed_shinies = False
        reset_completed_skins = False
        cleared_all_info = False
        reset_counter_to_default = False

        if ACTION_CLEAR_ALL_INFO in self.selected_values:
            quests.current_items.clear()
            quests.current_shinies.clear()
            quests.current_skins.clear()
            quests.completed_items.clear()
            quests.completed_shinies.clear()
            quests.completed_skins.clear()
            cleared_all_info = True
        else:
            if ACTION_RESET_COMPLETED_ITEMS in self.selected_values:
                quests.completed_items.clear()
                reset_completed_items = True
            if ACTION_RESET_COMPLETED_SHINIES in self.selected_values:
                quests.completed_shinies.clear()
                reset_completed_shinies = True
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
            selected_shiny_indexes = {
                int(value.split("::", 1)[1])
                for value in self.selected_values
                if value.startswith("shiny_idx::")
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
            selected_shiny_quests = {
                self.active_shiny_quests[idx]
                for idx in selected_shiny_indexes
                if 0 <= idx < len(self.active_shiny_quests)
            }

            if selected_item_quests:
                before = list(quests.current_items)
                quests.current_items = [q for q in quests.current_items if q not in selected_item_quests]
                removed_current_items = [q for q in before if q in selected_item_quests]

            if selected_skin_quests:
                before = list(quests.current_skins)
                quests.current_skins = [q for q in quests.current_skins if q not in selected_skin_quests]
                removed_current_skins = [q for q in before if q in selected_skin_quests]

            if selected_shiny_quests:
                before = list(quests.current_shinies)
                quests.current_shinies = [q for q in quests.current_shinies if q not in selected_shiny_quests]
                removed_current_shinies = [q for q in before if q in selected_shiny_quests]

            if removed_current_items or removed_current_shinies or removed_current_skins:
                regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
                refresh_player_quests(
                    player_data,
                    target_item_quests=regular_target,
                    target_shiny_quests=shiny_target,
                    target_skin_quests=skin_target,
                )

        if self.include_reset_counter_option and ACTION_RESET_RESETS_TO_DEFAULT in self.selected_values:
            player_data.quest_resets_remaining = self.default_reset_limit
            reset_counter_to_default = True

        if self.consume_reset_on_confirm:
            player_data.quest_resets_remaining = max(0, current_resets_remaining - 1)

        await save_player_records(interaction, records)

        summary_lines = [f"✅ Updated quest reset for {self.member.display_name}."]
        if removed_current_items:
            summary_lines.append(f"- Active item quests reset: {', '.join(removed_current_items)}")
        if removed_current_shinies:
            summary_lines.append(f"- Active shiny quests reset: {', '.join(removed_current_shinies)}")
        if removed_current_skins:
            summary_lines.append(f"- Active skin quests reset: {', '.join(removed_current_skins)}")
        if reset_completed_items:
            summary_lines.append("- Reset all completed item quests")
        if reset_completed_shinies:
            summary_lines.append("- Reset all completed shiny quests")
        if reset_completed_skins:
            summary_lines.append("- Reset all completed skin quests")
        if cleared_all_info:
            summary_lines.append("- Cleared all quest information")
        if reset_counter_to_default:
            summary_lines.append(f"- Reset quest reset attempts to default ({self.default_reset_limit})")

        if self.consume_reset_on_confirm:
            summary_lines.append(f"- Quest resets remaining: {player_data.quest_resets_remaining}")
            footer_line = "Use /myquests to verify the updated quest state."
        else:
            summary_lines.append(f"- Quest resets remaining: {player_data.quest_resets_remaining}")
            footer_line = "Use /viewquestsfor to verify the updated quest state."

        self.stop()
        await interaction.response.edit_message(
            content="\n".join(summary_lines + [footer_line]),
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

        config = await load_guild_config(interaction)
        default_reset_limit = config["quest_settings"]["num_resets"]

        player_data = records[key]
        resets_remaining = _coerce_resets_remaining(player_data, default_reset_limit)
        if player_data.quest_resets_remaining != resets_remaining:
            player_data.quest_resets_remaining = resets_remaining
            await save_player_records(interaction, records)

        active_item_quests = list(player_data.quests.current_items)
        active_shiny_quests = list(player_data.quests.current_shinies)
        active_skin_quests = list(player_data.quests.current_skins)

        view = ResetQuestSelectionView(
            actor_id=interaction.user.id,
            member=member,
            active_item_quests=active_item_quests,
            active_shiny_quests=active_shiny_quests,
            active_skin_quests=active_skin_quests,
            default_reset_limit=default_reset_limit,
            consume_reset_on_confirm=False,
            include_reset_counter_option=True,
        )

        menu_note = ""
        if view.omitted_active_options_count > 0:
            menu_note = (
                "\nNote: "
                f"{view.omitted_active_options_count} active quest option(s) are hidden due to Discord's 25-option menu limit."
            )

        await interaction.response.send_message(
            (
                f"Choose quest sections to reset for {member.display_name}.\n"
                f"Quest resets remaining: **{resets_remaining}**\n"
                "Active quests:\n"
                + "\n".join(_build_active_lines(active_item_quests, active_shiny_quests, active_skin_quests))
                + "\n\nAdditional options:\n"
                "- Reset all completed items\n"
                "- Reset all completed shinies\n"
                "- Reset all completed skins\n"
                "- Clear all quest information\n"
                f"- Reset quest reset attempts to default ({default_reset_limit})\n\n"
                "Select options below, then confirm or cancel."
                + menu_note
            ),
            view=view,
            ephemeral=True,
        )

    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)


async def command_self(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    try:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)

        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                "❌ You're not part of the PPE contest.",
                ephemeral=True,
            )

        config = await load_guild_config(interaction)
        default_reset_limit = config["quest_settings"]["num_resets"]

        player_data = records[key]
        resets_remaining = _coerce_resets_remaining(player_data, default_reset_limit)
        if player_data.quest_resets_remaining != resets_remaining:
            player_data.quest_resets_remaining = resets_remaining
            await save_player_records(interaction, records)

        if resets_remaining <= 0:
            return await interaction.response.send_message(
                "❌ You have no quest resets left.",
                ephemeral=True,
            )

        active_item_quests = list(player_data.quests.current_items)
        active_shiny_quests = list(player_data.quests.current_shinies)
        active_skin_quests = list(player_data.quests.current_skins)

        view = ResetQuestSelectionView(
            actor_id=interaction.user.id,
            member=interaction.user,
            active_item_quests=active_item_quests,
            active_shiny_quests=active_shiny_quests,
            active_skin_quests=active_skin_quests,
            default_reset_limit=default_reset_limit,
            consume_reset_on_confirm=True,
            include_reset_counter_option=False,
        )

        menu_note = ""
        if view.omitted_active_options_count > 0:
            menu_note = (
                "\nNote: "
                f"{view.omitted_active_options_count} active quest option(s) are hidden due to Discord's 25-option menu limit."
            )

        await interaction.response.send_message(
            (
                "Choose quest sections to reset.\n"
                f"Quest resets remaining: **{resets_remaining}**\n"
                "Active quests:\n"
                + "\n".join(_build_active_lines(active_item_quests, active_shiny_quests, active_skin_quests))
                + "\n\nAdditional options:\n"
                "- Reset all completed items\n"
                "- Reset all completed shinies\n"
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
