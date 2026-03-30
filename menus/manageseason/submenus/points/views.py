"""Points submenu views for /manageseason."""

from __future__ import annotations

import discord

from dataclass import ROTMG_CLASSES
from menus.manageseason.common import (
    build_class_modifier_settings_embed,
    build_global_modifier_settings_embed,
    build_point_settings_embed,
)
from menus.manageseason.modals import EditClassPointSettingsModal, EditGlobalPointSettingsModal
from menus.manageseason.services import load_points_settings_for_menu
from menus.menu_utils import OwnerBoundView


class ManagePointSettingsView(OwnerBoundView):
    """Landing view for point modifier workflows."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_point_settings_embed(self.settings)

    @discord.ui.button(label="Edit Global Modifiers", style=discord.ButtonStyle.success, row=0)
    async def edit_global(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageGlobalPointSettingsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Edit Class Modifiers", style=discord.ButtonStyle.success, row=0)
    async def edit_class(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageClassPointSettingsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


class ManageGlobalPointSettingsView(OwnerBoundView):
    """Subview for global modifier review and editing."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_global_modifier_settings_embed(self.settings)

    @discord.ui.button(label="Edit Global Modifiers", style=discord.ButtonStyle.success, row=0)
    async def edit_global(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditGlobalPointSettingsModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
                source_screen="global",
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class _ClassModifierSelect(discord.ui.Select):
    """Class selector used by class-modifier submenu."""

    def __init__(self, *, owner_id: int, selected_class: str | None) -> None:
        options: list[discord.SelectOption] = []
        for class_name in ROTMG_CLASSES:
            options.append(
                discord.SelectOption(
                    label=class_name,
                    value=class_name,
                    default=(class_name == selected_class),
                )
            )

        super().__init__(
            placeholder="Select a class to edit class-specific modifiers",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=0,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view = self.view
        if not isinstance(view, ManageClassPointSettingsView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return

        view.selected_class = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_class

        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageClassPointSettingsView(OwnerBoundView):
    """Subview for class modifier review and editing."""

    def __init__(self, *, owner_id: int, settings: dict, selected_class: str | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

        if selected_class in ROTMG_CLASSES:
            self.selected_class = selected_class
        elif ROTMG_CLASSES:
            self.selected_class = ROTMG_CLASSES[0]
        else:
            self.selected_class = None

        self.add_item(_ClassModifierSelect(owner_id=self.owner_id, selected_class=self.selected_class))

    def current_embed(self) -> discord.Embed:
        return build_class_modifier_settings_embed(self.settings, selected_class=self.selected_class)

    @discord.ui.button(label="Edit Selected Class", style=discord.ButtonStyle.success, row=1)
    async def edit_class(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.selected_class is None:
            await interaction.response.send_message("ERROR: Select a class first.", ephemeral=True)
            return

        self.settings = await load_points_settings_for_menu(interaction)
        existing_override = self.settings.get("class_overrides", {}).get(self.selected_class, {})
        await interaction.response.send_modal(
            EditClassPointSettingsModal(
                owner_id=self.owner_id,
                class_name=self.selected_class,
                source_message=interaction.message,
                existing_override=existing_override if isinstance(existing_override, dict) else None,
                source_screen="class",
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


__all__ = [
    "ManagePointSettingsView",
    "ManageGlobalPointSettingsView",
    "ManageClassPointSettingsView",
    "_ClassModifierSelect",
]
