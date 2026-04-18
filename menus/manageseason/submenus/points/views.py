"""Points submenu views for /manageseason."""

from __future__ import annotations

import logging

import discord

from dataclass import ROTMG_CLASSES
from menus.manageseason.common import (
    build_ppe_type_points_embed,
    get_ppe_type_multiplier_page_count,
    build_class_modifier_settings_embed,
    build_global_modifier_settings_embed,
    build_manage_duplicate_items_embed,
    build_manage_duplicate_mode_embed,
    build_point_settings_embed,
)
from menus.manageseason.modals import (
    BackfillLegacyPpeTypeFieldsModal,
    EditPenaltyBaseRatesModal,
    EditClassPointSettingsModal,
    EditIterativeBaseMultipliersModal,
    ComboOverrideSettingsModal,
    ComboShortcutModal,
    ResetAllPpeTypeOverridesModal,
    EditDuplicateItemPointsModal,
    EditGlobalPointSettingsModal,
    EditPetModifierModal,
    EditRarityModifiersModal,
)
from menus.manageseason.services import load_character_settings_for_menu, load_points_settings_for_menu
from menus.manageseason.services import update_duplicate_match_mode, update_top_point_mode
from utils.group_ppes import set_duo_partner, get_duo_partner
from utils.ppe_types import (
    build_ppe_type_options,
    get_ppe_type_multiplier_details_from_options,
    options_from_signature,
    ppe_type_compact_summary,
    ppe_type_display_from_options,
    ppe_type_option_signature,
)
from utils.wizard_components import (
    MinimumRarityContinueButton,
    MinimumRaritySelect,
    build_minimum_rarity_handlers,
    enforce_shiny_rarity_prompt,
    get_minimum_rarity_options,
    requires_enforce_shiny_rarity_choice,
)
from menus.menu_utils import OwnerBoundView


logger = logging.getLogger(__name__)


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

    @discord.ui.button(label="Edit PPE Type", style=discord.ButtonStyle.success, row=1)
    async def edit_ppe_type_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            character_settings = await load_character_settings_for_menu(interaction)
            view = ManagePpeTypePointSettingsView(owner_id=self.owner_id, character_settings=character_settings)
            await interaction.response.edit_message(embed=view.current_embed(), view=view)
        except Exception:
            logger.exception(
                "Failed to open ManagePpeTypePointSettingsView",
                extra={
                    "guild_id": getattr(getattr(interaction, "guild", None), "id", None),
                    "user_id": getattr(getattr(interaction, "user", None), "id", None),
                },
            )
            error_text = "ERROR: Could not open PPE Type settings. Check logs for details."
            if interaction.response.is_done():
                await interaction.followup.send(error_text, ephemeral=True)
            else:
                await interaction.response.send_message(error_text, ephemeral=True)

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


class ManagePpeTypePointSettingsView(OwnerBoundView):
    def __init__(self, *, owner_id: int, character_settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.character_settings = character_settings
        self.types_page_index = 0
        self._sync_types_pagination_buttons()

    def _sync_types_pagination_buttons(self) -> None:
        total_pages = get_ppe_type_multiplier_page_count(self.character_settings)
        disabled = total_pages <= 1
        self.prev_types_page.disabled = disabled
        self.next_types_page.disabled = disabled
        if total_pages > 0 and self.types_page_index >= total_pages:
            self.types_page_index = total_pages - 1

    def current_embed(self) -> discord.Embed:
        self._sync_types_pagination_buttons()
        return build_ppe_type_points_embed(self.character_settings, types_page_index=self.types_page_index)

    @discord.ui.button(label="Prev Types", style=discord.ButtonStyle.secondary, row=0)
    async def prev_types_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        total_pages = get_ppe_type_multiplier_page_count(self.character_settings)
        if total_pages <= 1:
            await interaction.response.edit_message(embed=self.current_embed(), view=self)
            return
        self.types_page_index = (self.types_page_index - 1) % total_pages
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next Types", style=discord.ButtonStyle.secondary, row=0)
    async def next_types_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        total_pages = get_ppe_type_multiplier_page_count(self.character_settings)
        if total_pages <= 1:
            await interaction.response.edit_message(embed=self.current_embed(), view=self)
            return
        self.types_page_index = (self.types_page_index + 1) % total_pages
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Edit Combo Multiplier", style=discord.ButtonStyle.success, row=1)
    async def edit_combo_override(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.character_settings = await load_character_settings_for_menu(interaction)
        await interaction.response.send_modal(
            ComboShortcutModal(
                owner_id=self.owner_id,
                source_message=interaction.message,
                character_settings=self.character_settings,
            )
        )

    @discord.ui.button(label="Edit Iterative Base Multipliers", style=discord.ButtonStyle.success, row=2)
    async def edit_iterative_base(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            self.character_settings = await load_character_settings_for_menu(interaction)
            await interaction.response.send_modal(
                EditIterativeBaseMultipliersModal(
                    owner_id=self.owner_id,
                    character_settings=self.character_settings,
                    source_message=interaction.message,
                )
            )
        except Exception as exc:
            error_text = f"ERROR: Could not open the iterative base multiplier editor: {exc}"
            if interaction.response.is_done():
                await interaction.followup.send(error_text, ephemeral=True)
            else:
                await interaction.response.send_message(error_text, ephemeral=True)

    @discord.ui.button(label="Backfill Legacy Fields", style=discord.ButtonStyle.danger, row=3)
    async def backfill_legacy_fields(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            BackfillLegacyPpeTypeFieldsModal(
                owner_id=self.owner_id,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Reset All Overrides", style=discord.ButtonStyle.danger, row=3)
    async def reset_all_overrides(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            ResetAllPpeTypeOverridesModal(
                owner_id=self.owner_id,
                source_message=interaction.message,
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class _ComboWizardYesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Yes", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(True)
        await view.advance(interaction)


class _ComboWizardNoButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="No", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        view._set_yes_no(False)
        await view.advance(interaction)


class _ComboWizardBackButton(discord.ui.Button):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=1, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await view.go_back(interaction)


class _ComboWizardOpenSettingsButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Set Combo Label & Multiplier", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        await interaction.response.send_modal(
            ComboOverrideSettingsModal(
                owner_id=view.owner_id,
                signature=view.signature,
                character_settings=view.character_settings,
                source_message=view.source_message,
                preset_name=view.combo_name,
                preset_short=view.combo_short,
            )
        )


class _ComboWizardSetDuoIdButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Set Duo Partner ID", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.send_modal(view.duo_partner_modal())


class _ComboWizardContinueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Continue", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        if bool(view.state.get("duo_enabled")) and not isinstance(view.state.get("duo_partner_id"), int):
            await interaction.response.send_message("Please set a valid duo partner Discord ID first.", ephemeral=True)
            return
        await view.advance(interaction)


class _ComboWizardCancelButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ManageComboMultiplierWizardView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return
        if interaction.user.id != view.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Cancelled combo edit.", embed=None, view=None)


class _ComboDuoPartnerIdModal(discord.ui.Modal, title="Set Duo Partner Discord ID"):
    partner_id = discord.ui.TextInput(
        label="Discord User ID",
        placeholder="Example: 123456789012345678",
        required=True,
        max_length=24,
    )

    def __init__(self, *, wizard: "ManageComboMultiplierWizardView") -> None:
        super().__init__(timeout=180)
        self.wizard = wizard

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.wizard.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        partner_text = str(self.partner_id.value or "").strip()
        if not partner_text.isdigit() or int(partner_text) <= 0:
            await interaction.response.send_message("Please enter a valid numeric Discord ID.", ephemeral=True)
            return

        partner_id = int(partner_text)
        self.wizard.state["duo_partner_id"] = partner_id
        
        # Save the duo partnership to the group_ppes file
        try:
            await set_duo_partner(interaction, self.wizard.owner_id, partner_id)
        except Exception as exc:
            await interaction.response.send_message(
                f"ERROR: Could not save duo partnership: {exc}",
                ephemeral=True,
            )
            return
        
        await interaction.response.send_message(
            f"Saved duo partner as <@{partner_text}>. Click Continue in the combo editor to finish.",
            ephemeral=True,
        )


class ManageComboMultiplierWizardView(OwnerBoundView):
    def __init__(
        self,
        *,
        owner_id: int,
        character_settings: dict,
        source_message: discord.Message | None,
        preset_signature: str | None = None,
        preset_options: dict | None = None,
        preset_name: str = "",
        preset_short: str = "",
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.character_settings = character_settings
        self.source_message = source_message
        self.state: dict[str, object] = {
            "regular": None,
            "uses_pet": True,
            "allows_tiered": True,
            "minimum_rarity": "common",
            "shiny_only": False,
            "enforce_rarity_on_shiny": False,
            "duo_enabled": False,
            "duo_partner_id": None,
        }
        self.history: list[str] = []

        self.signature = ""
        self.combo_name = str(preset_name or "").strip()
        self.combo_short = str(preset_short or "").strip()

        if isinstance(preset_options, dict) or preset_signature:
            options_source = preset_options if isinstance(preset_options, dict) else options_from_signature(preset_signature)
            if not isinstance(options_source, dict):
                options_source = {}
            options = build_ppe_type_options(
                regular=options_source.get("regular", True),
                uses_pet=options_source.get("uses_pet", True),
                allows_tiered=options_source.get("allows_tiered", True),
                minimum_rarity=options_source.get("minimum_rarity", "common"),
                shiny_only=options_source.get("shiny_only", False),
                enforce_rarity_on_shiny=options_source.get("enforce_rarity_on_shiny", False),
                duo_enabled=options_source.get("duo_enabled", False),
                duo_partner_id=options_source.get("duo_partner_id"),
            )
            self._apply_options(options)
            self.signature = ppe_type_option_signature(options)
            if not self.combo_name and not self.combo_short:
                entry = (
                    self.character_settings.get("combo_label_overrides", {})
                    if isinstance(self.character_settings.get("combo_label_overrides"), dict)
                    else {}
                )
                current = entry.get(self.signature, {}) if isinstance(entry.get(self.signature, {}), dict) else {}
                self.combo_name = str(current.get("name", "")).strip()
                self.combo_short = str(current.get("short", "")).strip()
            self.step = "summary"
        else:
            self.step = "regular"

        async def _refresh_minimum_rarity(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(embed=self.current_embed(), view=self)

        (
            self._minimum_rarity_on_selected,
            self._minimum_rarity_on_continue,
        ) = build_minimum_rarity_handlers(
            state=self.state,
            refresh=_refresh_minimum_rarity,
            advance=self.advance,
        )

        self._rebuild_items()

    def duo_partner_modal(self) -> discord.ui.Modal:
        return _ComboDuoPartnerIdModal(wizard=self)

    def _current_options(self) -> dict[str, object]:
        return build_ppe_type_options(
            regular=self.state.get("regular", True),
            uses_pet=self.state.get("uses_pet", True),
            allows_tiered=self.state.get("allows_tiered", True),
            minimum_rarity=self.state.get("minimum_rarity", "common"),
            shiny_only=self.state.get("shiny_only", False),
            enforce_rarity_on_shiny=self.state.get("enforce_rarity_on_shiny", False),
            duo_enabled=self.state.get("duo_enabled", False),
            duo_partner_id=self.state.get("duo_partner_id"),
        )

    def _apply_options(self, options: dict[str, object]) -> None:
        self.state["regular"] = bool(options.get("regular", True))
        self.state["uses_pet"] = bool(options.get("uses_pet", True))
        self.state["allows_tiered"] = bool(options.get("allows_tiered", True))
        self.state["minimum_rarity"] = str(options.get("minimum_rarity", "common"))
        self.state["shiny_only"] = bool(options.get("shiny_only", False))
        self.state["enforce_rarity_on_shiny"] = bool(options.get("enforce_rarity_on_shiny", False))
        self.state["duo_enabled"] = bool(options.get("duo_enabled", False))
        self.state["duo_partner_id"] = options.get("duo_partner_id")

    def _multiplier_hint(self, key: str, fallback: float) -> str:
        base = (
            self.character_settings.get("iterative_base_multipliers", {})
            if isinstance(self.character_settings.get("iterative_base_multipliers"), dict)
            else {}
        )
        multipliers = base if isinstance(base, dict) else {}
        try:
            value = float(multipliers.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        return f"x{value:.2f}"

    def _rarity_hint(self) -> str:
        base = (
            self.character_settings.get("iterative_base_multipliers", {})
            if isinstance(self.character_settings.get("iterative_base_multipliers"), dict)
            else {}
        )
        rarity = base.get("minimum_rarity", {}) if isinstance(base.get("minimum_rarity"), dict) else {}
        shiny_only = bool(self.state.get("shiny_only", False))
        available_options = get_minimum_rarity_options(shiny_only)

        fallback_map = {
            "all_shinies_allowed": 1.0,
            "common": 1.0,
            "uncommon": 1.1,
            "rare": 1.2,
            "legendary": 1.4,
            "divine": 1.5,
        }

        def _value(name: str, fallback: float) -> str:
            try:
                parsed = float(rarity.get(name, fallback))
            except (TypeError, ValueError):
                parsed = fallback
            if name == "all_shinies_allowed":
                return f"All Shinies Allowed {parsed:.2f}x"
            return f"{name.title()} {parsed:.2f}x"

        return ", ".join([_value(opt, fallback_map.get(opt, 1.0)) for opt in available_options])

    def _summary_embed(self) -> discord.Embed:
        options = self._current_options()
        breakdown = get_ppe_type_multiplier_details_from_options(options, self.character_settings)
        components = breakdown.get("components", []) if isinstance(breakdown.get("components", []), list) else []
        self.signature = str(breakdown.get("signature", self.signature or "")).strip().lower()
        combo_name = self.combo_name or self.signature
        combo_short = self.combo_short or ppe_type_compact_summary(options, ppe_settings=self.character_settings)
        display_name = ppe_type_display_from_options(options, ppe_settings=self.character_settings, compact=False)
        display_short = ppe_type_display_from_options(options, ppe_settings=self.character_settings, compact=True)
        source = str(breakdown.get("source", "base")).strip().lower()
        current_override_multiplier = float(breakdown.get("multiplier", 1.0))
        override_source = "Combo override" if source == "override" else "Iterative base"
        embed = discord.Embed(
            title="Combo Multiplier Summary",
            description="Review the selected combo values, then set the label and multiplier.",
            color=discord.Color.dark_teal(),
        )
        embed.add_field(
            name="Selected Values",
            value=(
                f"Regular: {'Yes' if bool(options.get('regular', True)) else 'No'}\n"
                f"Use Pet: {'Yes' if bool(options.get('uses_pet', True)) else 'No'}\n"
                f"Allow Tiered: {'Yes' if bool(options.get('allows_tiered', True)) else 'No'}\n"
                f"Minimum Rarity: {('All Shinies Allowed' if str(options.get('minimum_rarity', 'common')).strip().lower() == 'all_shinies_allowed' else str(options.get('minimum_rarity', 'common')).title())}\n"
                f"Shiny Only: {'Yes' if bool(options.get('shiny_only', False)) else 'No'}\n"
                f"Enforce Shiny Rarity: {'Yes' if bool(options.get('enforce_rarity_on_shiny', False)) else 'No'}\n"
                f"Duo: {'Yes' if bool(options.get('duo_enabled', False)) else 'No'}"
            ),
            inline=False,
        )
        component_lines = [
            f"• {str(line).strip()}"
            for line in breakdown.get("component_lines", [])
            if str(line).strip()
        ]
        if not component_lines:
            component_lines = ["• No combo-specific multipliers apply."]
        embed.add_field(
            name="Multipliers",
            value="\n".join(component_lines),
            inline=False,
        )
        embed.add_field(
            name="Final Multiplier",
            value=f"x{float(breakdown.get('multiplier', 1.0)):.2f}",
            inline=False,
        )
        embed.add_field(
            name="Resolved Display",
            value=f"Name: {display_name}\nShort: {display_short}",
            inline=False,
        )
        embed.add_field(
            name="Current Multiplier Source",
            value=f"{override_source}: x{current_override_multiplier:.2f}",
            inline=False,
        )
        embed.add_field(
            name="Signature",
            value=f"`{breakdown.get('signature', self.signature or 'pending')}`",
            inline=False,
        )
        return embed

    def current_embed(self) -> discord.Embed:
        if self.step == "summary":
            return self._summary_embed()
        prompt = self.prompt_text()
        embed = discord.Embed(
            title="Edit Combo Multiplier",
            description=prompt,
            color=discord.Color.dark_teal(),
        )
        return embed

    def prompt_text(self) -> str:
        if self.step == "regular":
            return "Is this combo a regular/duo PPE without other modifications?"
        if self.step == "uses_pet":
            return f"Does this combo use a pet? (No pet: {self._multiplier_hint('no_pet', 1.3)})"
        if self.step == "allows_tiered":
            return f"Does this combo allow tiered items? (No tiered: {self._multiplier_hint('no_tiered', 1.3)})"
        if self.step == "shiny_only":
            return f"Is this combo shiny only? (Yes: {self._multiplier_hint('shiny_only', 1.5)})"
        if self.step == "minimum_rarity":
            return f"What is the minimum rarity for this combo? ({self._rarity_hint()})"
        if self.step == "enforce_shiny":
            enforce_value = 0.9
            base = (
                self.character_settings.get("iterative_base_multipliers", {})
                if isinstance(self.character_settings.get("iterative_base_multipliers"), dict)
                else {}
            )
            try:
                enforce_value = float(base.get("enforce_shiny_rarity", 0.9))
            except (TypeError, ValueError):
                enforce_value = 0.9
            return enforce_shiny_rarity_prompt(self.state.get("minimum_rarity", "common"), enforce_value)
        if self.step == "duo":
            return f"Is this combo a duo ppe? (Yes: {self._multiplier_hint('duo', 0.6)})"
        if self.step == "duo_partner":
            partner_id = self.state.get("duo_partner_id")
            partner_line = f"Current duo partner: <@{partner_id}>" if isinstance(partner_id, int) else "Current duo partner: not set"
            return (
                "Enter the duo partner Discord ID.\n"
                "How to find it: User Settings -> Advanced -> Developer Mode ON, then right click your partner and Copy User ID.\n"
                f"{partner_line}"
            )
        return "Review the combo summary."

    def _set_yes_no(self, value: bool) -> None:
        if self.step == "regular":
            self.state["regular"] = value
        elif self.step == "uses_pet":
            self.state["uses_pet"] = value
        elif self.step == "allows_tiered":
            self.state["allows_tiered"] = value
        elif self.step == "shiny_only":
            self.state["shiny_only"] = value
        elif self.step == "enforce_shiny":
            self.state["enforce_rarity_on_shiny"] = value
        elif self.step == "duo":
            self.state["duo_enabled"] = value
            if not value:
                self.state["duo_partner_id"] = None

    def _next_step(self) -> str:
        if self.step == "regular":
            return "duo" if bool(self.state.get("regular")) else "uses_pet"
        if self.step == "uses_pet":
            return "allows_tiered"
        if self.step == "allows_tiered":
            return "shiny_only"
        if self.step == "shiny_only":
            return "minimum_rarity"
        if self.step == "minimum_rarity":
            if requires_enforce_shiny_rarity_choice(self.state.get("minimum_rarity", "common")):
                return "enforce_shiny"
            self.state["enforce_rarity_on_shiny"] = True
            return "duo"
        if self.step == "enforce_shiny":
            return "duo"
        if self.step == "duo":
            return "duo_partner" if bool(self.state.get("duo_enabled")) else "summary"
        if self.step == "duo_partner":
            return "summary"
        return "summary"

    async def advance(self, interaction: discord.Interaction) -> None:
        self.history.append(self.step)
        self.step = self._next_step()
        self._rebuild_items()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def go_back(self, interaction: discord.Interaction) -> None:
        if not self.history:
            await interaction.response.send_message("Already at the first step.", ephemeral=True)
            return

        self.step = self.history.pop()
        self._rebuild_items()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    def _rebuild_items(self) -> None:
        self.clear_items()
        if self.step in {"regular", "uses_pet", "allows_tiered", "shiny_only", "enforce_shiny", "duo"}:
            self.add_item(_ComboWizardYesButton())
            self.add_item(_ComboWizardNoButton())
            self.add_item(_ComboWizardBackButton(disabled=not bool(self.history)))
            self.add_item(_ComboWizardCancelButton())
            return
        if self.step == "minimum_rarity":
            self.add_item(
                MinimumRaritySelect(
                    selected=str(self.state.get("minimum_rarity", "common")),
                    owner_id=self.owner_id,
                    view_type=ManageComboMultiplierWizardView,
                    on_selected=self._minimum_rarity_on_selected,
                    shiny_only=bool(self.state.get("shiny_only", False)),
                )
            )
            self.add_item(
                MinimumRarityContinueButton(
                    owner_id=self.owner_id,
                    view_type=ManageComboMultiplierWizardView,
                    on_continue=self._minimum_rarity_on_continue,
                    row=1,
                )
            )
            self.add_item(_ComboWizardBackButton(disabled=not bool(self.history)))
            self.add_item(_ComboWizardCancelButton())
            return
        if self.step == "duo_partner":
            self.add_item(_ComboWizardSetDuoIdButton())
            self.add_item(_ComboWizardBackButton(disabled=not bool(self.history)))
            self.add_item(_ComboWizardContinueButton())
            self.add_item(_ComboWizardCancelButton())
            return
        if self.step == "summary":
            self.add_item(_ComboWizardOpenSettingsButton())
            self.add_item(_ComboWizardBackButton(disabled=not bool(self.history)))
            self.add_item(_ComboWizardCancelButton())


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
