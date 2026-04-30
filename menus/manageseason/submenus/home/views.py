"""Home submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import build_manageseason_home_embed
from menus.manageseason.services import (
    load_character_settings_for_menu,
    load_contest_settings_for_menu,
    load_points_settings_for_menu,
    reset_admin_tunable_settings_to_defaults,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView
from utils.ppe_types import normalize_allowed_ppe_types
from utils.guild_config import get_max_ppes


def _has_discord_administrator_permission(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


class ManageSeasonHomeView(OwnerBoundView):
    """Top-level /manageseason view with reset + settings navigation."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return build_manageseason_home_embed()

    @discord.ui.button(label="Reset Season", style=discord.ButtonStyle.danger, row=0)
    async def reset_season(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not _has_discord_administrator_permission(interaction):
            await interaction.response.send_message(
                "ERROR: `Reset Season` requires Discord Administrator permission.",
                ephemeral=True,
            )
            return

        from menus.manageseason.submenus.reset.views import ResetSeasonActionsView

        view = ResetSeasonActionsView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Point Settings", style=discord.ButtonStyle.success, row=0)
    async def manage_point_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.points.views import ManagePointSettingsView

        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Contests", style=discord.ButtonStyle.success, row=0)
    async def manage_contests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.contests.views import ManageContestsHomeView

        settings = await load_contest_settings_for_menu(interaction)
        view = ManageContestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Picture Suggestions", style=discord.ButtonStyle.success, row=1)
    async def picture_suggestions(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.picture_suggestions.entry import open_picture_suggestions_menu

        await open_picture_suggestions_menu(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Character Settings", style=discord.ButtonStyle.success, row=1)
    async def character_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.character_settings.views import ManageCharacterSettingsHomeView

        max_characters = await get_max_ppes(interaction)
        settings = await load_character_settings_for_menu(interaction)
        view = ManageCharacterSettingsHomeView(
            owner_id=self.owner_id,
            current_max_characters=max_characters,
            ppe_types_enabled=bool(settings.get("enable_ppe_types", True)),
            allowed_ppe_types=normalize_allowed_ppe_types(settings.get("allowed_ppe_types")),
            menu_character_creation=bool(settings.get("menu_character_creation", True)),
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Bot Cost", style=discord.ButtonStyle.primary, row=2)
    async def manage_bot_cost(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.cost.entry import open_manage_bot_cost_menu

        await open_manage_bot_cost_menu(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Factory Reset Settings", style=discord.ButtonStyle.danger, row=1)
    async def factory_reset_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not _has_discord_administrator_permission(interaction):
            await interaction.response.send_message(
                "ERROR: `Factory Reset Settings` requires Discord Administrator permission.",
                ephemeral=True,
            )
            return

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Factory Reset",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(
            (
                "WARNING: This will reset admin-tunable settings to defaults.\n"
                "This preserves sniffer endpoint and join embed message references.\n"
                "Proceed with factory reset?"
            ),
            ephemeral=True,
            view=confirm_view,
        )

        await confirm_view.wait()
        if confirm_view.confirmed is not True:
            status = "Factory reset cancelled." if confirm_view.confirmed is False else "Factory reset timed out."
            await interaction.edit_original_response(content=status, view=None)
            return

        summary = await reset_admin_tunable_settings_to_defaults(interaction)
        await interaction.edit_original_response(
            content=(
                "Factory settings reset complete.\n"
                f"endpoint_preserved: `{summary.endpoint_preserved}`\n"
                f"join_embed_preserved: `{summary.join_embed_preserved}`\n"
                f"picture_suggestion_channels_cleared: `{summary.picture_suggestion_channels_cleared}`"
            ),
            view=None,
        )


__all__ = ["ManageSeasonHomeView"]
