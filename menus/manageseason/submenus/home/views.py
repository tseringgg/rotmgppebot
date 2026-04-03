"""Home submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import build_manageseason_home_embed
from menus.manageseason.services import (
    load_character_settings_for_menu,
    load_contest_settings_for_menu,
    load_points_settings_for_menu,
)
from menus.menu_utils import OwnerBoundView
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

        from menus.manageseason.submenus.reset.views import ResetSeasonModeView

        view = ResetSeasonModeView(owner_id=self.owner_id)
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
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = ["ManageSeasonHomeView"]
