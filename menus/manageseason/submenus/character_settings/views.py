"""Character settings submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import build_character_settings_home_embed
from menus.manageseason.services import (
    load_character_settings_for_menu,
    update_allowed_ppe_types,
    update_max_characters_limit,
    update_ppe_type_feature_enabled,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView
from utils.ppe_types import all_ppe_types, normalize_allowed_ppe_types, ppe_type_label
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
        ppe_types_enabled: bool,
        allowed_ppe_types: list[str],
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.current_limit = int(current_limit)
        self.source_message = source_message
        self.ppe_types_enabled = bool(ppe_types_enabled)
        self.allowed_ppe_types = normalize_allowed_ppe_types(allowed_ppe_types)
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
                ppe_types_enabled=self.ppe_types_enabled,
                allowed_ppe_types=self.allowed_ppe_types,
            )
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass


class ManageCharacterSettingsHomeView(OwnerBoundView):
    """Landing view for character settings in /manageseason."""

    def __init__(
        self,
        *,
        owner_id: int,
        current_max_characters: int,
        ppe_types_enabled: bool,
        allowed_ppe_types: list[str],
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.current_max_characters = int(current_max_characters)
        self.ppe_types_enabled = bool(ppe_types_enabled)
        self.allowed_ppe_types = normalize_allowed_ppe_types(allowed_ppe_types)

    def current_embed(self) -> discord.Embed:
        return build_character_settings_home_embed(
            current_max_characters=self.current_max_characters,
            ppe_types_enabled=self.ppe_types_enabled,
            allowed_ppe_types=self.allowed_ppe_types,
        )

    @discord.ui.button(label="Change Max Characters", style=discord.ButtonStyle.success, row=0)
    async def change_max_characters(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        modal = ChangeMaxCharactersModal(
            owner_id=self.owner_id,
            current_limit=self.current_max_characters,
            source_message=interaction.message,
            ppe_types_enabled=self.ppe_types_enabled,
            allowed_ppe_types=self.allowed_ppe_types,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Enable/Disable PPE Types", style=discord.ButtonStyle.success, row=0)
    async def toggle_ppe_types(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await update_ppe_type_feature_enabled(interaction, enabled=not self.ppe_types_enabled)
        self.ppe_types_enabled = bool(settings.get("enable_ppe_types", True))
        self.allowed_ppe_types = normalize_allowed_ppe_types(settings.get("allowed_ppe_types"))
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Choose Allowed Character Types", style=discord.ButtonStyle.primary, row=1)
    async def choose_allowed_types(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ManageAllowedPpeTypesView(
            owner_id=self.owner_id,
            current_max_characters=self.current_max_characters,
            ppe_types_enabled=self.ppe_types_enabled,
            allowed_ppe_types=self.allowed_ppe_types,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


class _AllowedPpeTypesSelect(discord.ui.Select):
    def __init__(self, *, selected_types: list[str]) -> None:
        options = [
            discord.SelectOption(
                label=ppe_type_label(ppe_type),
                value=ppe_type,
                default=(ppe_type in selected_types),
            )
            for ppe_type in all_ppe_types()
        ]
        super().__init__(
            placeholder="Choose allowed PPE types",
            min_values=1,
            max_values=len(options),
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageAllowedPpeTypesView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view.selected_types = normalize_allowed_ppe_types(list(self.values))
        for option in self.options:
            option.default = option.value in view.selected_types
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageAllowedPpeTypesView(OwnerBoundView):
    def __init__(
        self,
        *,
        owner_id: int,
        current_max_characters: int,
        ppe_types_enabled: bool,
        allowed_ppe_types: list[str],
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.current_max_characters = int(current_max_characters)
        self.ppe_types_enabled = bool(ppe_types_enabled)
        self.selected_types = normalize_allowed_ppe_types(allowed_ppe_types)
        self.add_item(_AllowedPpeTypesSelect(selected_types=self.selected_types))

    def current_embed(self) -> discord.Embed:
        return build_character_settings_home_embed(
            current_max_characters=self.current_max_characters,
            ppe_types_enabled=self.ppe_types_enabled,
            allowed_ppe_types=self.selected_types,
        )

    @discord.ui.button(label="Save Allowed Types", style=discord.ButtonStyle.success, row=1)
    async def save_allowed_types(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        saved = await update_allowed_ppe_types(interaction, allowed_types=self.selected_types)
        refreshed = ManageCharacterSettingsHomeView(
            owner_id=self.owner_id,
            current_max_characters=self.current_max_characters,
            ppe_types_enabled=bool(saved.get("enable_ppe_types", True)),
            allowed_ppe_types=normalize_allowed_ppe_types(saved.get("allowed_ppe_types")),
        )
        await interaction.response.edit_message(embed=refreshed.current_embed(), view=refreshed)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_character_settings_for_menu(interaction)
        refreshed = ManageCharacterSettingsHomeView(
            owner_id=self.owner_id,
            current_max_characters=self.current_max_characters,
            ppe_types_enabled=bool(settings.get("enable_ppe_types", True)),
            allowed_ppe_types=normalize_allowed_ppe_types(settings.get("allowed_ppe_types")),
        )
        await interaction.response.edit_message(embed=refreshed.current_embed(), view=refreshed)


__all__ = ["ManageCharacterSettingsHomeView"]
