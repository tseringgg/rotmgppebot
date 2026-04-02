"""Character settings submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import build_character_settings_home_embed
from menus.manageseason.services import update_max_characters_limit
from menus.menu_utils import ConfirmCancelView, OwnerBoundView
from utils.guild_config import get_max_ppes
from utils.player_records import load_player_records


class ChangeMaxCharactersModal(discord.ui.Modal, title="Change Max Characters"):
    """Modal to update max allowed PPE characters per player."""

    new_limit = discord.ui.TextInput(
        label="New max characters",
        placeholder="Enter a positive whole number",
        required=True,
        max_length=4,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        current_limit: int,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.current_limit = int(current_limit)
        self.source_message = source_message
        self.new_limit.default = str(int(current_limit))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        text = str(self.new_limit.value or "").strip()
        if not text.isdigit():
            await interaction.response.send_message("ERROR: Enter a positive whole number.", ephemeral=True)
            return

        parsed_limit = int(text)
        if parsed_limit <= 0:
            await interaction.response.send_message("ERROR: Max characters must be at least 1.", ephemeral=True)
            return

        use_followup_for_result = False
        if parsed_limit < self.current_limit:
            records = await load_player_records(interaction)
            projected_deletions = sum(max(0, len(player_data.ppes) - parsed_limit) for player_data in records.values())

            confirm_view = ConfirmCancelView(
                owner_id=self.owner_id,
                timeout=90,
                confirm_label="Apply Limit",
                cancel_label="Cancel",
                confirm_style=discord.ButtonStyle.danger,
                cancel_style=discord.ButtonStyle.secondary,
                owner_error="This confirmation belongs to another user.",
            )

            await interaction.response.send_message(
                "⚠️ Reducing max characters will delete excess characters.\n"
                f"Current limit: **{self.current_limit}** -> New limit: **{parsed_limit}**\n"
                f"Projected deletions: **{projected_deletions}** character(s).\n"
                "Deletion order: lowest-point inactive characters first.",
                view=confirm_view,
                ephemeral=True,
            )
            await confirm_view.wait()

            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass

            if not confirm_view.confirmed:
                await interaction.followup.send("Character limit update cancelled.", ephemeral=True)
                return
            use_followup_for_result = True

        summary = await update_max_characters_limit(interaction, new_limit=parsed_limit)

        if summary.new_limit < summary.old_limit:
            warning_lines = [
                f"⚠️ Limit reduced from **{summary.old_limit}** to **{summary.new_limit}**.",
                "Excess characters were deleted starting from the worst inactive characters first.",
                f"Deleted characters: **{summary.characters_deleted}** across **{summary.players_trimmed}** player(s).",
                f"Inactive deleted: **{summary.inactive_characters_deleted}** | Active deleted: **{summary.active_characters_deleted}**",
            ]
            if summary.characters_deleted == 0:
                warning_lines.append("No players were over the new cap, so no characters were deleted.")
            response_text = "\n".join(warning_lines)
        elif summary.new_limit == summary.old_limit:
            response_text = f"No change. Max characters remains **{summary.new_limit}**."
        else:
            response_text = (
                f"✅ Max characters increased from **{summary.old_limit}** to **{summary.new_limit}**."
            )

        if use_followup_for_result:
            await interaction.followup.send(response_text, ephemeral=True)
        else:
            await interaction.response.send_message(response_text, ephemeral=True)

        if self.source_message is not None:
            refreshed_limit = await get_max_ppes(interaction)
            refreshed_view = ManageCharacterSettingsHomeView(
                owner_id=self.owner_id,
                current_max_characters=refreshed_limit,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass


class ManageCharacterSettingsHomeView(OwnerBoundView):
    """Landing view for character settings in /manageseason."""

    def __init__(self, *, owner_id: int, current_max_characters: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.current_max_characters = int(current_max_characters)

    def current_embed(self) -> discord.Embed:
        return build_character_settings_home_embed(current_max_characters=self.current_max_characters)

    @discord.ui.button(label="Change Max Characters", style=discord.ButtonStyle.success, row=0)
    async def change_max_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        modal = ChangeMaxCharactersModal(
            owner_id=self.owner_id,
            current_limit=self.current_max_characters,
            source_message=interaction.message,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


__all__ = ["ManageCharacterSettingsHomeView"]
