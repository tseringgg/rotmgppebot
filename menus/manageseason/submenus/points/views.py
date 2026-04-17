"""Points submenu views for /manageseason."""

from __future__ import annotations

import discord

from dataclass import ROTMG_CLASSES
from menus.manageseason.common import (
    build_ppe_type_points_embed,
    build_class_modifier_settings_embed,
    build_global_modifier_settings_embed,
    build_manage_duplicate_items_embed,
    build_manage_duplicate_mode_embed,
    build_point_settings_embed,
)
from menus.manageseason.modals import (
    EditPenaltyBaseRatesModal,
    EditClassPointSettingsModal,
    EditDuplicateItemPointsModal,
    EditGlobalPointSettingsModal,
    EditPetModifierModal,
    EditPpeTypeMultiplierModal,
    EditRarityModifiersModal,
)
from menus.manageseason.services import load_character_settings_for_menu, load_points_settings_for_menu
from menus.manageseason.services import update_duplicate_match_mode, update_top_point_mode
from utils.ppe_types import all_ppe_types, ppe_type_label
from menus.menu_utils import OwnerBoundView


class ManagePointSettingsView(OwnerBoundView):
    """Landing view for point modifier workflows."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_point_settings_embed(self.settings)

    @discord.ui.button(label="Adjust Top Points", style=discord.ButtonStyle.success, row=3)
    async def adjust_top_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageTopPointSettingsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

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

    @discord.ui.button(label="Edit PPE Type Points", style=discord.ButtonStyle.success, row=1)
    async def edit_ppe_type_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        character_settings = await load_character_settings_for_menu(interaction)
        view = ManagePpeTypePointSettingsView(owner_id=self.owner_id, character_settings=character_settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Penalty Reduction Modifiers", style=discord.ButtonStyle.success, row=2)
    async def edit_pet_modifiers(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditPetModifierModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Edit Penalty Base Rates", style=discord.ButtonStyle.success, row=2)
    async def edit_penalty_base_rates(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditPenaltyBaseRatesModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Manage Duplicate Items", style=discord.ButtonStyle.success, row=1)
    async def manage_duplicate_items(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageDuplicateItemsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Edit Rarity Modifiers", style=discord.ButtonStyle.success, row=1)
    async def edit_rarity_modifiers(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditRarityModifiersModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Manage Set Completion Points", style=discord.ButtonStyle.success, row=2)
    async def manage_set_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.sets.views import ManageSetPointsView

        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageSetPointsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=4)
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


class _PpeTypeSelect(discord.ui.Select):
    def __init__(self, *, selected_type: str) -> None:
        options = [
            discord.SelectOption(label=ppe_type_label(ppe_type), value=ppe_type, default=(ppe_type == selected_type))
            for ppe_type in all_ppe_types()
        ]
        super().__init__(
            placeholder="Select a PPE type to edit its multiplier",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManagePpeTypePointSettingsView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view.selected_type = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_type
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManagePpeTypePointSettingsView(OwnerBoundView):
    def __init__(self, *, owner_id: int, character_settings: dict, selected_type: str | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.character_settings = character_settings
        all_types = all_ppe_types()
        self.selected_type = selected_type if selected_type in all_types else all_types[0]
        self.add_item(_PpeTypeSelect(selected_type=self.selected_type))

    def current_embed(self) -> discord.Embed:
        return build_ppe_type_points_embed(self.character_settings)

    @discord.ui.button(label="Edit Selected PPE Type", style=discord.ButtonStyle.success, row=1)
    async def edit_selected_type(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.character_settings = await load_character_settings_for_menu(interaction)
        multipliers = (
            self.character_settings.get("ppe_type_multipliers", {})
            if isinstance(self.character_settings.get("ppe_type_multipliers"), dict)
            else {}
        )
        await interaction.response.send_modal(
            EditPpeTypeMultiplierModal(
                owner_id=self.owner_id,
                ppe_type=self.selected_type,
                current_value=float(multipliers.get(self.selected_type, 1.0)),
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageDuplicateItemsView(OwnerBoundView):
    """Subview for duplicate-point settings and duplicate matching definitions."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_manage_duplicate_items_embed(self.settings)

    @discord.ui.button(label="Edit Duplicate Item Points", style=discord.ButtonStyle.success, row=0)
    async def edit_duplicate_item_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditDuplicateItemPointsModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
                source_screen="duplicate_items",
            )
        )

    @discord.ui.button(label="Manage What Is Duplicate", style=discord.ButtonStyle.success, row=0)
    async def manage_what_is_duplicate(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageDuplicateModeView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class _DuplicateModeSelect(discord.ui.Select):
    def __init__(self, *, owner_id: int, selected_mode: str) -> None:
        options = [
            discord.SelectOption(
                label="Different rarities are separate",
                value="separate_rarity",
                description="Default: item + rarity + shiny must match to be duplicate.",
                default=selected_mode == "separate_rarity",
            ),
            discord.SelectOption(
                label="Any rarity of same item is duplicate",
                value="any_rarity",
                description="Item + shiny match counts as duplicate across rarities.",
                default=selected_mode == "any_rarity",
            ),
            discord.SelectOption(
                label="Divines are exempt; others group",
                value="non_divine_any_rarity",
                description="Divines never count as duplicate copies.",
                default=selected_mode == "non_divine_any_rarity",
            ),
            discord.SelectOption(
                label="All variants including shinies group",
                value="all_including_shiny",
                description="Only item name matters for duplicate matching.",
                default=selected_mode == "all_including_shiny",
            ),
        ]
        super().__init__(
            placeholder="Choose duplicate matching mode",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageDuplicateModeView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view.selected_mode = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_mode
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageDuplicateModeView(OwnerBoundView):
    """Subview for selecting how duplicate matching groups item copies."""

    def __init__(self, *, owner_id: int, settings: dict, selected_mode: str | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        mode = str(settings.get("duplicate_match_mode", "separate_rarity")).strip().lower()
        if selected_mode in {"separate_rarity", "any_rarity", "non_divine_any_rarity", "all_including_shiny"}:
            mode = selected_mode
        self.selected_mode = mode if mode in {"separate_rarity", "any_rarity", "non_divine_any_rarity", "all_including_shiny"} else "separate_rarity"
        self.add_item(_DuplicateModeSelect(owner_id=self.owner_id, selected_mode=self.selected_mode))

    def current_embed(self) -> discord.Embed:
        return build_manage_duplicate_mode_embed(self.settings)

    @discord.ui.button(label="Apply Selected Mode", style=discord.ButtonStyle.success, row=1)
    async def apply_selected_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings, refresh_summary = await update_duplicate_match_mode(
            interaction,
            duplicate_match_mode=self.selected_mode,
        )

        self.settings = settings
        await interaction.response.edit_message(embed=self.current_embed(), view=self)
        await interaction.followup.send(
            "Updated duplicate matching mode.\n"
            f"Mode: {str(settings.get('duplicate_match_mode', self.selected_mode)).replace('_', ' ').title()}\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManageDuplicateItemsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class _TopPointModeSelect(discord.ui.Select):
    def __init__(self, *, owner_id: int, selected_mode: str) -> None:
        options = [
            discord.SelectOption(
                label="Current Behavior",
                value="current",
                description="Keep Tops repeatable with the current scoring behavior.",
                default=selected_mode == "current",
            ),
            discord.SelectOption(
                label="Points Once",
                value="once",
                description="Tops only score the first time they are logged.",
                default=selected_mode == "once",
            ),
            discord.SelectOption(
                label="No Points",
                value="none",
                description="Tops still log seasonally but never award points.",
                default=selected_mode == "none",
            ),
        ]
        super().__init__(
            placeholder="Choose how Tops should score",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageTopPointSettingsView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view.selected_mode = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_mode
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageTopPointSettingsView(OwnerBoundView):
    def __init__(self, *, owner_id: int, settings: dict, selected_mode: str | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

        mode = str(settings.get("tops_point_mode", "current")).strip().lower()
        if selected_mode in {"current", "once", "none"}:
            mode = selected_mode
        self.selected_mode = mode if mode in {"current", "once", "none"} else "current"

        self.add_item(_TopPointModeSelect(owner_id=self.owner_id, selected_mode=self.selected_mode))

    def current_embed(self) -> discord.Embed:
        return build_point_settings_embed(self.settings)

    @discord.ui.button(label="Apply Selected Mode", style=discord.ButtonStyle.success, row=1)
    async def apply_selected_mode(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        settings, refresh_summary = await update_top_point_mode(
            interaction,
            tops_point_mode=self.selected_mode,
        )

        self.settings = settings
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

        await interaction.followup.send(
            "Updated top point handling.\n"
            f"Mode: {str(settings.get('tops_point_mode', self.selected_mode)).title()}\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
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
    "ManageDuplicateItemsView",
    "ManageDuplicateModeView",
    "ManagePpeTypePointSettingsView",
    "ManageTopPointSettingsView",
    "_ClassModifierSelect",
]
