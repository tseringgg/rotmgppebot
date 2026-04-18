"""Modal workflows for editing point settings from /manageseason."""

from __future__ import annotations

import discord

from utils.ppe_types import (
    PPE_MIN_RARITY_ORDER,
    find_ppe_type_by_label,
    find_combo_label_override,
    get_ppe_type_multiplier_details_from_options,
    legacy_ppe_type_to_options,
    normalize_combo_signature,
    normalize_iterative_combo_overrides,
    normalize_ppe_combo_label_overrides,
    options_from_signature,
    ppe_type_compact_summary,
    ppe_type_display_from_options,
    ppe_type_label,
    ppe_type_option_signature,
    ppe_type_short_label,
)
from utils.group_ppes import get_duo_partner
from menus.manageseason.services import (
    backfill_legacy_ppe_type_options,
    clear_all_ppe_type_overrides,
    clear_ppe_type_display_override,
    load_character_settings_for_menu,
    load_points_settings_for_menu,
    set_combo_display_override,
    set_iterative_combo_multiplier_override,
    update_class_point_override,
    update_duplicate_match_mode,
    update_duplicate_item_point_reduction,
    update_global_point_modifiers,
    update_combo_multiplier_details,
    update_iterative_base_option_multipliers,
    update_penalty_base_rates,
    update_pet_point_modifiers,
    update_ppe_type_display_overrides,
    update_ppe_type_multipliers,
    update_rarity_multipliers,
)
from menus.menu_utils import ConfirmCancelView


def _parse_optional_float(raw_value: str, *, field_name: str) -> float | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"ERROR: `{field_name}` must be a number (for example: `5`, `-2.5`, `0`).") from exc


def _parse_optional_rarity_multiplier_set(raw_value: str) -> dict[str, float] | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    values = [segment.strip() for segment in text.split(",") if segment.strip()]
    if len(values) != 5:
        raise ValueError(
            "ERROR: `rarity_multipliers` must contain 5 comma-separated numbers in this order: common, uncommon, rare, legendary, divine."
        )

    keys = ("common", "uncommon", "rare", "legendary", "divine")
    parsed_values: dict[str, float] = {}
    for key, value_text in zip(keys, values):
        try:
            parsed_values[key] = float(value_text)
        except ValueError as exc:
            raise ValueError(
                "ERROR: `rarity_multipliers` must contain only numbers separated by commas."
            ) from exc
    return parsed_values


def _parse_minimum_total(raw_value: str) -> tuple[float | None, bool]:
    """Parse minimum_total input and detect explicit clear intent."""
    text = str(raw_value or "").strip()
    if not text:
        return None, False

    lowered = text.casefold()
    if lowered in {"none", "clear", "null", "remove"}:
        return None, True

    try:
        return float(text), False
    except ValueError as exc:
        raise ValueError(
            "ERROR: `minimum_total` must be a number, or use `none` to clear the minimum-total floor."
        ) from exc


def _parse_minimum_rarity_multipliers(raw_value: str) -> dict[str, float] | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    values = [segment.strip() for segment in text.split(",") if segment.strip()]
    if len(values) != len(PPE_MIN_RARITY_ORDER):
        raise ValueError(
            "ERROR: `minimum_rarity_multipliers` must contain 5 comma-separated numbers in this order: common, uncommon, rare, legendary, divine."
        )

    parsed_values: list[float] = []
    for value_text in values:
        try:
            parsed_values.append(float(value_text))
        except ValueError as exc:
            raise ValueError(
                "ERROR: `minimum_rarity_multipliers` must contain only numbers separated by commas."
            ) from exc

    return dict(zip(PPE_MIN_RARITY_ORDER, parsed_values))


def _parse_shiny_multiplier_pair(raw_value: str) -> tuple[float, float] | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    parts = [segment.strip() for segment in text.split(",") if segment.strip()]
    if len(parts) != 2:
        raise ValueError(
            "ERROR: `shiny_multipliers` must contain exactly 2 comma-separated numbers in this order: shiny_only, enforce_shiny_rarity."
        )

    try:
        shiny_only = float(parts[0])
        enforce_shiny = float(parts[1])
    except ValueError as exc:
        raise ValueError(
            "ERROR: `shiny_multipliers` must contain only numbers separated by a comma."
        ) from exc

    return shiny_only, enforce_shiny


async def _confirm_points_update(
    *,
    interaction: discord.Interaction,
    owner_id: int,
    confirmation_text: str,
) -> bool:
    confirm_view = ConfirmCancelView(
        owner_id=owner_id,
        timeout=60,
        confirm_label="Apply Changes",
        cancel_label="Cancel",
        confirm_style=discord.ButtonStyle.danger,
        cancel_style=discord.ButtonStyle.secondary,
        owner_error="This confirmation belongs to another user.",
    )

    await interaction.response.send_message(confirmation_text, view=confirm_view, ephemeral=True)
    await confirm_view.wait()

    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        pass

    if not confirm_view.confirmed:
        await interaction.followup.send("Point modifier update cancelled.", ephemeral=True)
        return False
    return True


async def _refresh_point_settings_message(
    *,
    interaction: discord.Interaction,
    owner_id: int,
    source_message: discord.Message | None,
    settings: dict | None = None,
    source_screen: str = "landing",
    selected_class: str | None = None,
) -> None:
    if source_message is None:
        return

    from menus.manageseason.submenus.points.views import (
        ManageClassPointSettingsView,
        ManageDuplicateItemsView,
        ManageDuplicateModeView,
        ManageGlobalPointSettingsView,
        ManagePpeTypePointSettingsView,
        ManagePointSettingsView,
    )

    refreshed = settings if settings is not None else await load_points_settings_for_menu(interaction)
    if source_screen == "global":
        view = ManageGlobalPointSettingsView(owner_id=owner_id, settings=refreshed)
    elif source_screen == "class":
        view = ManageClassPointSettingsView(owner_id=owner_id, settings=refreshed, selected_class=selected_class)
    elif source_screen == "duplicate_items":
        view = ManageDuplicateItemsView(owner_id=owner_id, settings=refreshed)
    elif source_screen == "duplicate_mode":
        view = ManageDuplicateModeView(owner_id=owner_id, settings=refreshed)
    elif source_screen == "ppe_type":
        character_settings = await load_character_settings_for_menu(interaction)
        view = ManagePpeTypePointSettingsView(owner_id=owner_id, character_settings=character_settings)
    else:
        view = ManagePointSettingsView(owner_id=owner_id, settings=refreshed)

    try:
        await source_message.edit(embed=view.current_embed(), view=view)
    except discord.HTTPException:
        if interaction.response.is_done():
            await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)


class EditGlobalPointSettingsModal(discord.ui.Modal, title="Edit Global Point Modifiers"):
    """Edit loot/bonus/penalty/total global percent modifiers."""

    loot_percent = discord.ui.TextInput(
        label="Loot Percent",
        placeholder="Example: 5 or -2.5",
        required=False,
        max_length=20,
    )
    bonus_percent = discord.ui.TextInput(
        label="Bonus Percent",
        placeholder="Example: 10",
        required=False,
        max_length=20,
    )
    penalty_percent = discord.ui.TextInput(
        label="Penalty Percent",
        placeholder="Example: -5",
        required=False,
        max_length=20,
    )
    total_percent = discord.ui.TextInput(
        label="Total Percent",
        placeholder="Example: 0",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
        source_screen: str = "landing",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.source_screen = source_screen

        global_settings = settings.get("global", {}) if isinstance(settings.get("global"), dict) else {}
        self.loot_percent.default = f"{float(global_settings.get('loot_percent', 0.0)):.2f}"
        self.bonus_percent.default = f"{float(global_settings.get('bonus_percent', 0.0)):.2f}"
        self.penalty_percent.default = f"{float(global_settings.get('penalty_percent', 0.0)):.2f}"
        self.total_percent.default = f"{float(global_settings.get('total_percent', 0.0)):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            loot_percent = _parse_optional_float(self.loot_percent.value, field_name="loot_percent")
            bonus_percent = _parse_optional_float(self.bonus_percent.value, field_name="bonus_percent")
            penalty_percent = _parse_optional_float(self.penalty_percent.value, field_name="penalty_percent")
            total_percent = _parse_optional_float(self.total_percent.value, field_name="total_percent")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if all(value is None for value in (loot_percent, bonus_percent, penalty_percent, total_percent)):
            await interaction.response.send_message("ERROR: Provide at least one modifier to update.", ephemeral=True)
            return

        loot_text = self.loot_percent.value.strip() or "(unchanged)"
        bonus_text = self.bonus_percent.value.strip() or "(unchanged)"
        penalty_text = self.penalty_percent.value.strip() or "(unchanged)"
        total_text = self.total_percent.value.strip() or "(unchanged)"
        confirm_text = (
            "⚠️ **Apply global modifier changes and recalculate all PPE characters?**\n"
            "This will update point totals server-wide.\n\n"
            f"Loot: `{loot_text}`\n"
            f"Bonus: `{bonus_text}`\n"
            f"Penalty: `{penalty_text}`\n"
            f"Total: `{total_text}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_global_point_modifiers(
            interaction,
            loot_percent=loot_percent,
            bonus_percent=bonus_percent,
            penalty_percent=penalty_percent,
            total_percent=total_percent,
        )

        global_settings = settings.get("global", {})
        await interaction.followup.send(
            "Updated global point modifiers.\n"
            f"Loot: {float(global_settings.get('loot_percent', 0.0)):.2f}%\n"
            f"Bonus: {float(global_settings.get('bonus_percent', 0.0)):.2f}%\n"
            f"Penalty: {float(global_settings.get('penalty_percent', 0.0)):.2f}%\n"
            f"Total: {float(global_settings.get('total_percent', 0.0)):.2f}%\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen=self.source_screen,
        )


class EditPetModifierModal(discord.ui.Modal, title="Penalty Reduction Modifiers"):
    pet_level_percent_reduction = discord.ui.TextInput(
        label="Pet Level Reduction Rate (% per level)",
        placeholder="Example: 0.1",
        required=False,
        max_length=20,
    )
    exalts_percent_reduction = discord.ui.TextInput(
        label="Exalts Reduction Rate (% per exalt)",
        placeholder="Example: 0.1",
        required=False,
        max_length=20,
    )
    loot_percent_reduction = discord.ui.TextInput(
        label="Loot Boost Reduction Rate (% per 1% boost)",
        placeholder="Example: 0.1",
        required=False,
        max_length=20,
    )
    incombat_percent_reduction = discord.ui.TextInput(
        label="In-Combat Reduction Rate (% per 1.0s)",
        placeholder="Example: 0.1",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
        source_screen: str = "landing",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.source_screen = source_screen

        modifiers = (
            settings.get("starting_penalty_modifiers", {})
            if isinstance(settings.get("starting_penalty_modifiers"), dict)
            else {}
        )
        self.pet_level_percent_reduction.default = f"{float(modifiers.get('pet_level_percent_reduction', 0.0)):.2f}"
        self.exalts_percent_reduction.default = f"{float(modifiers.get('exalts_percent_reduction', 0.0)):.2f}"
        self.loot_percent_reduction.default = f"{float(modifiers.get('loot_percent_reduction', 0.0)):.2f}"
        self.incombat_percent_reduction.default = f"{float(modifiers.get('incombat_percent_reduction', 0.0)):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            pet_level_percent_reduction = _parse_optional_float(
                self.pet_level_percent_reduction.value,
                field_name="pet_level_percent_reduction",
            )
            exalts_percent_reduction = _parse_optional_float(
                self.exalts_percent_reduction.value,
                field_name="exalts_percent_reduction",
            )
            loot_percent_reduction = _parse_optional_float(
                self.loot_percent_reduction.value,
                field_name="loot_percent_reduction",
            )
            incombat_percent_reduction = _parse_optional_float(
                self.incombat_percent_reduction.value,
                field_name="incombat_percent_reduction",
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if all(
            value is None
            for value in (
                pet_level_percent_reduction,
                exalts_percent_reduction,
                loot_percent_reduction,
                incombat_percent_reduction,
            )
        ):
            await interaction.response.send_message("ERROR: Provide at least one modifier to update.", ephemeral=True)
            return

        confirm_text = (
            "⚠️ **Apply penalty reduction modifier changes and recalculate all PPE characters?**\n"
            "These rates stack additively to reduce item points per starting stat unit.\n\n"
            f"Pet Level Reduction: `{self.pet_level_percent_reduction.value or '(unchanged)'}`\n"
            f"Exalts Reduction: `{self.exalts_percent_reduction.value or '(unchanged)'}`\n"
            f"Loot Boost Reduction: `{self.loot_percent_reduction.value or '(unchanged)'}`\n"
            f"In-Combat Reduction: `{self.incombat_percent_reduction.value or '(unchanged)'}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_pet_point_modifiers(
            interaction,
            pet_level_percent_reduction=pet_level_percent_reduction,
            exalts_percent_reduction=exalts_percent_reduction,
            loot_percent_reduction=loot_percent_reduction,
            incombat_percent_reduction=incombat_percent_reduction,
        )

        modifiers = settings.get("starting_penalty_modifiers", {})

        await interaction.followup.send(
            "Updated starting penalty reduction modifiers.\n"
            f"Pet Level Reduction: {float(modifiers.get('pet_level_percent_reduction', 0.0)):.2f}%\n"
            f"Exalts Reduction: {float(modifiers.get('exalts_percent_reduction', 0.0)):.2f}%\n"
            f"Loot Boost Reduction: {float(modifiers.get('loot_percent_reduction', 0.0)):.2f}%\n"
            f"In-Combat Reduction: {float(modifiers.get('incombat_percent_reduction', 0.0)):.2f}%\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen=self.source_screen,
        )


class EditPenaltyBaseRatesModal(discord.ui.Modal, title="Edit Penalty Base Rates"):
    pet_points_per_level = discord.ui.TextInput(
        label="Pet Level Rate (pts per level)",
        placeholder="Example: -0.25",
        required=False,
        max_length=20,
    )
    exalts_points_per_exalt = discord.ui.TextInput(
        label="Exalts Rate (pts per exalt)",
        placeholder="Example: -0.50",
        required=False,
        max_length=20,
    )
    loot_points_per_percent = discord.ui.TextInput(
        label="Loot Boost Rate (pts per 1% boost)",
        placeholder="Example: -2.00",
        required=False,
        max_length=20,
    )
    incombat_points_per_second = discord.ui.TextInput(
        label="In-Combat Rate (pts per 1.0s)",
        placeholder="Example: -2.00",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
        source_screen: str = "landing",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.source_screen = source_screen

        weights = settings.get("penalty_weights", {}) if isinstance(settings.get("penalty_weights"), dict) else {}
        try:
            pet_level_per_point = float(weights.get("pet_level_per_point", 4.0))
        except (TypeError, ValueError):
            pet_level_per_point = 4.0
        try:
            exalts_per_point = float(weights.get("exalts_per_point", 2.0))
        except (TypeError, ValueError):
            exalts_per_point = 2.0
        try:
            loot_percent_per_point = float(weights.get("loot_percent_per_point", 0.5))
        except (TypeError, ValueError):
            loot_percent_per_point = 0.5
        try:
            incombat_seconds_per_point = float(weights.get("incombat_seconds_per_point", 0.1))
        except (TypeError, ValueError):
            incombat_seconds_per_point = 0.1

        self.pet_points_per_level.default = f"{(-1.0 / pet_level_per_point):.2f}" if pet_level_per_point > 0 else "0.00"
        self.exalts_points_per_exalt.default = f"{(-1.0 / exalts_per_point):.2f}" if exalts_per_point > 0 else "0.00"
        self.loot_points_per_percent.default = f"{(-1.0 / loot_percent_per_point):.2f}" if loot_percent_per_point > 0 else "0.00"
        self.incombat_points_per_second.default = f"{(-1.0 / incombat_seconds_per_point):.2f}" if incombat_seconds_per_point > 0 else "0.00"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            pet_points_per_level = _parse_optional_float(
                self.pet_points_per_level.value,
                field_name="pet_points_per_level",
            )
            exalts_points_per_exalt = _parse_optional_float(
                self.exalts_points_per_exalt.value,
                field_name="exalts_points_per_exalt",
            )
            loot_points_per_percent = _parse_optional_float(
                self.loot_points_per_percent.value,
                field_name="loot_points_per_percent",
            )
            incombat_points_per_second = _parse_optional_float(
                self.incombat_points_per_second.value,
                field_name="incombat_points_per_second",
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if all(
            value is None
            for value in (
                pet_points_per_level,
                exalts_points_per_exalt,
                loot_points_per_percent,
                incombat_points_per_second,
            )
        ):
            await interaction.response.send_message("ERROR: Provide at least one base rate to update.", ephemeral=True)
            return

        confirm_text = (
            "⚠️ **Apply penalty base-rate changes and recalculate all PPE characters?**\n"
            "These rates define how starting penalty points are generated.\n\n"
            f"Pet Level Rate: `{self.pet_points_per_level.value or '(unchanged)'}`\n"
            f"Exalts Rate: `{self.exalts_points_per_exalt.value or '(unchanged)'}`\n"
            f"Loot Boost Rate: `{self.loot_points_per_percent.value or '(unchanged)'}`\n"
            f"In-Combat Rate: `{self.incombat_points_per_second.value or '(unchanged)'}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_penalty_base_rates(
            interaction,
            pet_points_per_level=pet_points_per_level,
            exalts_points_per_exalt=exalts_points_per_exalt,
            loot_points_per_percent=loot_points_per_percent,
            incombat_points_per_second=incombat_points_per_second,
        )

        weights = settings.get("penalty_weights", {}) if isinstance(settings.get("penalty_weights"), dict) else {}
        try:
            pet_level_per_point = float(weights.get("pet_level_per_point", 4.0))
        except (TypeError, ValueError):
            pet_level_per_point = 4.0
        try:
            exalts_per_point = float(weights.get("exalts_per_point", 2.0))
        except (TypeError, ValueError):
            exalts_per_point = 2.0
        try:
            loot_percent_per_point = float(weights.get("loot_percent_per_point", 0.5))
        except (TypeError, ValueError):
            loot_percent_per_point = 0.5
        try:
            incombat_seconds_per_point = float(weights.get("incombat_seconds_per_point", 0.1))
        except (TypeError, ValueError):
            incombat_seconds_per_point = 0.1

        summary_lines = ["Updated penalty base rates."]
        summary_lines.append(
            f"Pet Level Rate: {(-1.0 / pet_level_per_point):.2f} pts/level" if pet_level_per_point > 0 else "Pet Level Rate: 0.00 pts/level"
        )
        summary_lines.append(
            f"Exalts Rate: {(-1.0 / exalts_per_point):.2f} pts/exalt" if exalts_per_point > 0 else "Exalts Rate: 0.00 pts/exalt"
        )
        summary_lines.append(
            f"Loot Boost Rate: {(-1.0 / loot_percent_per_point):.2f} pts/1% boost" if loot_percent_per_point > 0 else "Loot Boost Rate: 0.00 pts/1% boost"
        )
        summary_lines.append(
            f"In-Combat Rate: {(-1.0 / incombat_seconds_per_point):.2f} pts/1.0s" if incombat_seconds_per_point > 0 else "In-Combat Rate: 0.00 pts/1.0s"
        )
        summary_lines.append(f"PPEs recalculated: {refresh_summary.ppes_processed}")
        summary_lines.append(f"PPE totals changed: {refresh_summary.ppes_updated}")

        await interaction.followup.send(
            "\n".join(summary_lines),
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen=self.source_screen,
        )


class EditClassPointSettingsModal(discord.ui.Modal):
    """Edit class-specific percent modifiers and optional minimum total floor."""

    loot_percent = discord.ui.TextInput(
        label="Loot Percent",
        placeholder="Leave blank to keep unchanged",
        required=False,
        max_length=20,
    )
    bonus_percent = discord.ui.TextInput(
        label="Bonus Percent",
        placeholder="Leave blank to keep unchanged",
        required=False,
        max_length=20,
    )
    penalty_percent = discord.ui.TextInput(
        label="Penalty Percent",
        placeholder="Leave blank to keep unchanged",
        required=False,
        max_length=20,
    )
    total_percent = discord.ui.TextInput(
        label="Total Percent",
        placeholder="Leave blank to keep unchanged",
        required=False,
        max_length=20,
    )
    minimum_total = discord.ui.TextInput(
        label="Minimum Total",
        placeholder="Number, or 'none' to clear minimum floor",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        class_name: str,
        source_message: discord.Message | None,
        existing_override: dict | None = None,
        source_screen: str = "class",
    ) -> None:
        super().__init__(title=f"Edit Class Modifiers - {class_name}", timeout=300)
        self.owner_id = owner_id
        self.class_name = class_name
        self.source_message = source_message
        self.source_screen = source_screen

        override = existing_override if isinstance(existing_override, dict) else {}
        self.loot_percent.default = f"{float(override.get('loot_percent', 0.0)):.2f}"
        self.bonus_percent.default = f"{float(override.get('bonus_percent', 0.0)):.2f}"
        self.penalty_percent.default = f"{float(override.get('penalty_percent', 0.0)):.2f}"
        self.total_percent.default = f"{float(override.get('total_percent', 0.0)):.2f}"

        current_minimum = override.get("minimum_total")
        if current_minimum is not None:
            self.minimum_total.default = f"{float(current_minimum):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            loot_percent = _parse_optional_float(self.loot_percent.value, field_name="loot_percent")
            bonus_percent = _parse_optional_float(self.bonus_percent.value, field_name="bonus_percent")
            penalty_percent = _parse_optional_float(self.penalty_percent.value, field_name="penalty_percent")
            total_percent = _parse_optional_float(self.total_percent.value, field_name="total_percent")
            minimum_total, clear_minimum_total = _parse_minimum_total(self.minimum_total.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if all(value is None for value in (loot_percent, bonus_percent, penalty_percent, total_percent, minimum_total)) and not clear_minimum_total:
            await interaction.response.send_message("ERROR: Provide at least one class modifier to update.", ephemeral=True)
            return

        minimum_text = self.minimum_total.value.strip() or "(unchanged)"
        confirm_text = (
            f"⚠️ **Apply class modifier changes for {self.class_name} and recalculate all PPE characters?**\n"
            "This will update point totals server-wide.\n\n"
            f"Loot: `{self.loot_percent.value or '(unchanged)'}`\n"
            f"Bonus: `{self.bonus_percent.value or '(unchanged)'}`\n"
            f"Penalty: `{self.penalty_percent.value or '(unchanged)'}`\n"
            f"Total: `{self.total_percent.value or '(unchanged)'}`\n"
            f"Minimum Total: `{minimum_text}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, class_override, refresh_summary = await update_class_point_override(
            interaction,
            class_name=self.class_name,
            loot_percent=loot_percent,
            bonus_percent=bonus_percent,
            penalty_percent=penalty_percent,
            total_percent=total_percent,
            minimum_total=minimum_total,
            clear_minimum_total=clear_minimum_total,
        )

        min_total = class_override.get("minimum_total")
        min_text = "none" if min_total is None else f"{float(min_total):.2f}"
        await interaction.followup.send(
            f"Updated class override for {self.class_name}.\n"
            f"Loot: {float(class_override.get('loot_percent', 0.0)):.2f}%\n"
            f"Bonus: {float(class_override.get('bonus_percent', 0.0)):.2f}%\n"
            f"Penalty: {float(class_override.get('penalty_percent', 0.0)):.2f}%\n"
            f"Total: {float(class_override.get('total_percent', 0.0)):.2f}%\n"
            f"Minimum total: {min_text}\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen=self.source_screen,
            selected_class=self.class_name,
        )


class EditPpeTypeMultiplierModal(discord.ui.Modal):
    multiplier = discord.ui.TextInput(
        label="Multiplier",
        placeholder="Example: 1.3",
        required=True,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_type: str,
        current_value: float,
        source_message: discord.Message | None,
    ) -> None:
        short_label = ppe_type_short_label(ppe_type)
        super().__init__(title=f"Edit PPE Multiplier - {short_label}", timeout=300)
        self.owner_id = owner_id
        self.ppe_type = ppe_type
        self.source_message = source_message
        self.multiplier.default = f"{float(current_value):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            parsed = float(str(self.multiplier.value).strip())
        except ValueError:
            await interaction.response.send_message("ERROR: Multiplier must be a number.", ephemeral=True)
            return

        if parsed <= 0:
            await interaction.response.send_message("ERROR: Multiplier must be greater than 0.", ephemeral=True)
            return

        character_settings = await load_character_settings_for_menu(interaction)
        multipliers = (
            dict(character_settings.get("ppe_type_multipliers", {}))
            if isinstance(character_settings.get("ppe_type_multipliers"), dict)
            else {}
        )
        multipliers[self.ppe_type] = parsed

        confirm_text = (
            f"⚠️ **Apply PPE type multiplier update for {ppe_type_label(self.ppe_type)}?**\n"
            "This will recalculate all PPE characters.\n\n"
            f"New multiplier: `{parsed:.2f}x`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_ppe_type_multipliers(
            interaction,
            multipliers=multipliers,
        )

        await interaction.followup.send(
            f"Updated {ppe_type_label(self.ppe_type)} multiplier to {float(settings.get('ppe_type_multipliers', {}).get(self.ppe_type, parsed)):.2f}x.\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
        )


class EditPpeTypeLabelModal(discord.ui.Modal):
    full_name = discord.ui.TextInput(
        label="Display Name",
        placeholder="Example: Divine & Shiny PPE",
        required=False,
        max_length=80,
    )
    short_name = discord.ui.TextInput(
        label="Short Label",
        placeholder="Example: D+SPE",
        required=False,
        max_length=40,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        ppe_type: str,
        character_settings: dict,
        source_message: discord.Message | None,
    ) -> None:
        short_label = ppe_type_short_label(ppe_type, ppe_settings=character_settings)
        super().__init__(title=f"Edit Type Label - {short_label}", timeout=300)
        self.owner_id = owner_id
        self.ppe_type = ppe_type
        self.source_message = source_message

        labels = character_settings.get("type_label_overrides", {}) if isinstance(character_settings.get("type_label_overrides", {}), dict) else {}
        shorts = character_settings.get("type_short_label_overrides", {}) if isinstance(character_settings.get("type_short_label_overrides", {}), dict) else {}
        self.full_name.default = str(labels.get(ppe_type, ""))
        self.short_name.default = str(shorts.get(ppe_type, ""))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        full_name = str(self.full_name.value or "").strip()
        short_name = str(self.short_name.value or "").strip()

        if not full_name and not short_name:
            settings = await clear_ppe_type_display_override(
                interaction,
                ppe_type=self.ppe_type,
            )
            await interaction.response.send_message(
                f"Cleared custom label override for {ppe_type_label(self.ppe_type)}.",
                ephemeral=True,
            )
        else:
            settings = await update_ppe_type_display_overrides(
                interaction,
                label_overrides={self.ppe_type: full_name} if full_name else {},
                short_label_overrides={self.ppe_type: short_name} if short_name else {},
            )
            await interaction.response.send_message(
                f"Updated custom label for {ppe_type_label(self.ppe_type)}.",
                ephemeral=True,
            )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class EditIterativeBaseMultipliersModal(discord.ui.Modal, title="Edit Iterative Base Multipliers"):
    no_pet = discord.ui.TextInput(label="No Pet Multiplier", placeholder="1.3", required=False, max_length=20)
    no_tiered = discord.ui.TextInput(label="No Tiered Multiplier", placeholder="1.3", required=False, max_length=20)
    minimum_rarity_multipliers = discord.ui.TextInput(
        label="Rarity Multipliers (C,U,R,L,D)",
        placeholder="1.00, 1.10, 1.20, 1.40, 1.50",
        required=False,
        max_length=120,
    )
    shiny_multipliers = discord.ui.TextInput(
        label="Shiny Multipliers (only,enforce)",
        placeholder="1.50, 1.00",
        required=False,
        max_length=40,
    )
    duo = discord.ui.TextInput(label="Duo Multiplier", placeholder="0.6", required=False, max_length=20)

    def __init__(self, *, owner_id: int, character_settings: dict, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        base = character_settings.get("iterative_base_multipliers", {}) if isinstance(character_settings.get("iterative_base_multipliers", {}), dict) else {}
        self.no_pet.default = f"{float(base.get('no_pet', 1.3)):.2f}"
        self.no_tiered.default = f"{float(base.get('no_tiered', 1.3)):.2f}"
        rarity = base.get("minimum_rarity", {}) if isinstance(base.get("minimum_rarity"), dict) else {}
        self.minimum_rarity_multipliers.default = ", ".join(
            f"{float(rarity.get(name, default)):.2f}"
            for name, default in zip(PPE_MIN_RARITY_ORDER, [1.0, 1.1, 1.2, 1.4, 1.5])
        )
        self.shiny_multipliers.default = (
            f"{float(base.get('shiny_only', 1.5)):.2f}, {float(base.get('enforce_shiny_rarity', 1.0)):.2f}"
        )
        self.duo.default = f"{float(base.get('duo', 0.6)):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            no_pet = _parse_optional_float(self.no_pet.value, field_name="no_pet")
            no_tiered = _parse_optional_float(self.no_tiered.value, field_name="no_tiered")
            minimum_rarity_multipliers = _parse_minimum_rarity_multipliers(self.minimum_rarity_multipliers.value)
            shiny_pair = _parse_shiny_multiplier_pair(self.shiny_multipliers.value)
            duo = _parse_optional_float(self.duo.value, field_name="duo")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        character_settings = await load_character_settings_for_menu(interaction)
        base = character_settings.get("iterative_base_multipliers", {}) if isinstance(character_settings.get("iterative_base_multipliers", {}), dict) else {}
        updated = dict(base)
        if no_pet is not None:
            updated["no_pet"] = no_pet
        if no_tiered is not None:
            updated["no_tiered"] = no_tiered
        if minimum_rarity_multipliers is not None:
            updated["minimum_rarity"] = minimum_rarity_multipliers
        if shiny_pair is not None:
            updated["shiny_only"] = shiny_pair[0]
            updated["enforce_shiny_rarity"] = shiny_pair[1]
        if duo is not None:
            updated["duo"] = duo

        settings, refresh_summary = await update_iterative_base_option_multipliers(
            interaction,
            multipliers=updated,
        )
        await interaction.response.send_message(
            "Updated iterative base multipliers.\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )
        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class EditIterativeComboMultiplierModal(discord.ui.Modal, title="Edit Combo Multiplier Override"):
    signature = discord.ui.TextInput(
        label="Combination Signature",
        placeholder="pet:yes|tiered:no|minimum:divine|shiny:yes|enforce_shiny_rarity:yes|duo:no",
        required=True,
        max_length=220,
    )
    multiplier = discord.ui.TextInput(
        label="Override Multiplier (blank to remove)",
        placeholder="Example: 5.0",
        required=False,
        max_length=20,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None, character_settings: dict | None = None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        if isinstance(character_settings, dict):
            overrides = character_settings.get("iterative_combo_overrides", {}) if isinstance(character_settings.get("iterative_combo_overrides", {}), dict) else {}
            if overrides:
                first_key = sorted(overrides.keys())[0]
                self.signature.default = first_key
                self.multiplier.default = f"{float(overrides[first_key]):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        signature = str(self.signature.value or "").strip().lower()
        multiplier_text = str(self.multiplier.value or "").strip()
        parsed_multiplier: float | None = None
        if multiplier_text:
            try:
                parsed_multiplier = float(multiplier_text)
            except ValueError:
                await interaction.response.send_message("Multiplier must be a number.", ephemeral=True)
                return
            if parsed_multiplier <= 0:
                await interaction.response.send_message("Multiplier must be greater than 0.", ephemeral=True)
                return

        settings, refresh_summary = await set_iterative_combo_multiplier_override(
            interaction,
            signature=signature,
            multiplier=parsed_multiplier,
        )
        action_text = "Updated" if parsed_multiplier is not None else "Removed"
        await interaction.response.send_message(
            f"{action_text} combo multiplier override for `{signature}`.\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )
        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class ComboShortcutModal(discord.ui.Modal, title="Edit Combo Multiplier"):
    shortcut = discord.ui.TextInput(
        label="Type Label, Short Label, or Signature",
        placeholder="Enter PPE label/combo label. Type N/A to label new combo.",
        required=True,
        max_length=220,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None, character_settings: dict | None = None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.character_settings = character_settings if isinstance(character_settings, dict) else {}

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        raw_value = str(self.shortcut.value or "").strip()
        if not raw_value:
            await interaction.response.send_message("Please enter a short label, signature, or N/A.", ephemeral=True)
            return

        # Load duo partner from group_ppes
        duo_partner_id = None
        try:
            duo_partner_id = await get_duo_partner(interaction, self.owner_id)
        except Exception:
            pass  # If loading fails, just continue without the duo partner

        if raw_value.casefold() != "n/a":
            resolved = find_combo_label_override(raw_value, self.character_settings)
            resolved_type = find_ppe_type_by_label(raw_value, self.character_settings)
            options = options_from_signature(raw_value)

            settings = self.character_settings if isinstance(self.character_settings, dict) else {}
            candidate_signatures: set[str] = set()
            combo_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
            combo_labels = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))
            observed_raw = settings.get("observed_combo_signatures")
            observed_signatures = observed_raw if isinstance(observed_raw, list) else []
            for raw_signature in list(combo_overrides.keys()) + list(combo_labels.keys()) + observed_signatures:
                normalized_signature = normalize_combo_signature(raw_signature)
                if normalized_signature and normalized_signature != "regular":
                    candidate_signatures.add(normalized_signature)

            resolved_signature_by_display: str | None = None
            needle = raw_value.strip().casefold()
            for signature in sorted(candidate_signatures):
                signature_options = options_from_signature(signature)
                if not isinstance(signature_options, dict):
                    continue
                display_name = ppe_type_display_from_options(
                    signature_options,
                    ppe_settings=settings,
                    compact=False,
                ).strip().casefold()
                display_short = ppe_type_display_from_options(
                    signature_options,
                    ppe_settings=settings,
                    compact=True,
                ).strip().casefold()
                if needle in {display_name, display_short}:
                    resolved_signature_by_display = signature
                    break

            if resolved is None and resolved_type is None and options is None and resolved_signature_by_display is None:
                await interaction.response.send_message(
                    "No matching combo, PPE type label, short label, or signature was found. Use N/A to build a new combo from scratch.",
                    ephemeral=True,
                )
                return

            if resolved is not None:
                signature = resolved[0]
                label_entry = resolved[1]
                display_name = str(label_entry.get("name", "")).strip()
                short_name = str(label_entry.get("short", "")).strip()
                preset_options = options_from_signature(signature)
            elif resolved_type is not None:
                preset_options = legacy_ppe_type_to_options(resolved_type)
                signature = ppe_type_option_signature(preset_options)
                display_name = ppe_type_label(resolved_type, ppe_settings=self.character_settings)
                short_name = ppe_type_short_label(resolved_type, ppe_settings=self.character_settings)
            elif resolved_signature_by_display is not None:
                signature = resolved_signature_by_display
                preset_options = options_from_signature(signature)
                if not isinstance(preset_options, dict):
                    await interaction.response.send_message(
                        "The matched combo signature could not be parsed. Try using N/A to rebuild it.",
                        ephemeral=True,
                    )
                    return
                display_name = ppe_type_display_from_options(
                    preset_options,
                    ppe_settings=self.character_settings,
                    compact=False,
                )
                short_name = ppe_type_display_from_options(
                    preset_options,
                    ppe_settings=self.character_settings,
                    compact=True,
                )
            else:
                preset_options = options
                signature = ppe_type_option_signature(options)
                display_name = ""
                short_name = ""

            # Include duo partner in preset options if available
            if isinstance(preset_options, dict) and duo_partner_id:
                preset_options["duo_partner_id"] = duo_partner_id

            from menus.manageseason.submenus.points.views import ManageComboMultiplierWizardView

            wizard = ManageComboMultiplierWizardView(
                owner_id=self.owner_id,
                character_settings=self.character_settings,
                source_message=self.source_message,
                preset_signature=signature,
                preset_options=preset_options,
                preset_name=display_name,
                preset_short=short_name,
            )
            if self.source_message is None:
                await interaction.response.send_message(embed=wizard.current_embed(), view=wizard, ephemeral=True)
                return

            await interaction.response.send_message("Opening combo editor...", ephemeral=True)
            try:
                await self.source_message.edit(embed=wizard.current_embed(), view=wizard)
            except discord.HTTPException:
                await interaction.followup.send(embed=wizard.current_embed(), view=wizard, ephemeral=True)
            return

        from menus.manageseason.submenus.points.views import ManageComboMultiplierWizardView

        wizard = ManageComboMultiplierWizardView(
            owner_id=self.owner_id,
            character_settings=self.character_settings,
            source_message=self.source_message,
        )
        
        # Set duo partner from group_ppes if available
        if duo_partner_id:
            wizard.state["duo_partner_id"] = duo_partner_id
        
        if self.source_message is None:
            await interaction.response.send_message(embed=wizard.current_embed(), view=wizard, ephemeral=True)
            return

        await interaction.response.send_message("Opening combo editor...", ephemeral=True)
        try:
            await self.source_message.edit(embed=wizard.current_embed(), view=wizard)
        except discord.HTTPException:
            await interaction.followup.send(embed=wizard.current_embed(), view=wizard, ephemeral=True)


class ComboOverrideSettingsModal(discord.ui.Modal):
    display_name = discord.ui.TextInput(
        label="Display Name",
        placeholder="Example: Divine & Shiny PPE",
        required=False,
        max_length=80,
    )
    short_name = discord.ui.TextInput(
        label="Short Label",
        placeholder="Example: D+SPE",
        required=False,
        max_length=40,
    )
    multiplier = discord.ui.TextInput(
        label="Combo Multiplier Override (blank to remove)",
        placeholder="Example: 5.0",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        signature: str,
        character_settings: dict | None = None,
        source_message: discord.Message | None,
        preset_name: str = "",
        preset_short: str = "",
    ) -> None:
        super().__init__(title="Set Combo Label & Multiplier", timeout=300)
        self.owner_id = owner_id
        self.signature = normalize_combo_signature(signature)
        self.source_message = source_message

        settings = character_settings if isinstance(character_settings, dict) else {}
        overrides = normalize_ppe_combo_label_overrides(settings.get("combo_label_overrides"))
        label_entry = overrides.get(self.signature, {}) if isinstance(overrides.get(self.signature, {}), dict) else {}
        multiplier_overrides = normalize_iterative_combo_overrides(settings.get("iterative_combo_overrides"))
        options = options_from_signature(self.signature)

        fallback_full = ""
        fallback_short = ""
        computed_multiplier: float | None = None
        if isinstance(options, dict):
            fallback_full = self.signature
            fallback_short = ppe_type_compact_summary(options, ppe_settings=settings)
            details = get_ppe_type_multiplier_details_from_options(options, settings)
            computed_multiplier = float(details.get("multiplier", 1.0))

        preset_name = str(preset_name or "").strip()
        preset_short = str(preset_short or "").strip()
        self.display_name.default = preset_name or str(label_entry.get("name", "")).strip() or fallback_full
        self.short_name.default = preset_short or str(label_entry.get("short", "")).strip() or fallback_short
        if self.signature in multiplier_overrides:
            self.multiplier.default = f"{float(multiplier_overrides[self.signature]):.2f}"
        elif computed_multiplier is not None:
            self.multiplier.default = f"{computed_multiplier:.2f}"
        else:
            self.multiplier.default = ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            parsed_multiplier = _parse_optional_float(self.multiplier.value, field_name="multiplier")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        display_name = str(self.display_name.value or "").strip()
        short_name = str(self.short_name.value or "").strip()

        if parsed_multiplier is not None and parsed_multiplier <= 0:
            await interaction.response.send_message("ERROR: Multiplier must be greater than 0.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        settings, refresh_summary = await update_combo_multiplier_details(
            interaction,
            signature=self.signature,
            multiplier=parsed_multiplier,
            name=display_name or None,
            short=short_name or None,
        )

        action_text = "Cleared" if parsed_multiplier is None and not display_name and not short_name else "Updated"

        await interaction.followup.send(
            f"{action_text} combo override for `{self.signature}`.\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class ResetAllPpeTypeOverridesModal(discord.ui.Modal, title="Reset All PPE Overrides"):
    confirm = discord.ui.TextInput(
        label="Type RESET to confirm",
        placeholder="RESET",
        required=True,
        max_length=20,
    )
    reset_scope = discord.ui.TextInput(
        label="Reset Scope (all or combo)",
        placeholder="all",
        required=False,
        max_length=20,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        if str(self.confirm.value or "").strip().upper() != "RESET":
            await interaction.response.send_message("Cancelled. You must type RESET exactly.", ephemeral=True)
            return

        scope_raw = str(self.reset_scope.value or "").strip().lower()
        if scope_raw in {"", "all", "everything"}:
            clear_type_labels = True
            clear_message = "Cleared all PPE type/combo label and combo multiplier overrides."
        elif scope_raw in {"combo", "combos", "combo-only", "combo_only"}:
            clear_type_labels = False
            clear_message = "Cleared combo label and combo multiplier overrides (type label overrides kept)."
        else:
            await interaction.response.send_message(
                "ERROR: Reset Scope must be `all` or `combo`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        settings, refresh_summary = await clear_all_ppe_type_overrides(
            interaction,
            clear_type_labels=clear_type_labels,
        )
        await interaction.followup.send(
            f"{clear_message}\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class EditPpeComboLabelModal(discord.ui.Modal, title="Edit Combo Label Override"):
    signature = discord.ui.TextInput(
        label="Combination Signature",
        placeholder="Example: pet:yes|tiered:no|minimum:divine|shiny:yes|enforce_shiny_rarity:yes|duo:no",
        required=True,
        max_length=220,
    )
    full_name = discord.ui.TextInput(
        label="Display Name",
        placeholder="Example: Divine & Shiny PPE",
        required=False,
        max_length=80,
    )
    short_name = discord.ui.TextInput(
        label="Short Label",
        placeholder="Example: D+SPE",
        required=False,
        max_length=40,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        source_message: discord.Message | None,
        default_signature: str = "",
        character_settings: dict | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.signature.default = default_signature

        if isinstance(character_settings, dict) and default_signature:
            overrides = character_settings.get("combo_label_overrides", {}) if isinstance(character_settings.get("combo_label_overrides", {}), dict) else {}
            existing = overrides.get(default_signature, {}) if isinstance(overrides.get(default_signature, {}), dict) else {}
            self.full_name.default = str(existing.get("name", ""))
            self.short_name.default = str(existing.get("short", ""))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        signature = str(self.signature.value or "").strip().lower()
        full_name = str(self.full_name.value or "").strip()
        short_name = str(self.short_name.value or "").strip()

        try:
            settings = await set_combo_display_override(
                interaction,
                signature=signature,
                name=full_name or None,
                short=short_name or None,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if not full_name and not short_name:
            await interaction.response.send_message(f"Cleared combo label override for `{signature}`.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Updated combo label override for `{signature}`.", ephemeral=True)

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
            settings=settings,
        )


class BackfillLegacyPpeTypeFieldsModal(discord.ui.Modal, title="Backfill Legacy PPE Type Fields"):
    confirm = discord.ui.TextInput(
        label="Type BACKFILL to continue",
        placeholder="BACKFILL",
        required=True,
        max_length=20,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return
        if str(self.confirm.value or "").strip().upper() != "BACKFILL":
            await interaction.response.send_message("Cancelled. You must type BACKFILL exactly.", ephemeral=True)
            return

        players_touched, ppes_touched = await backfill_legacy_ppe_type_options(interaction)
        await interaction.response.send_message(
            f"Legacy backfill complete. Players updated: {players_touched}, PPEs updated: {ppes_touched}.",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            source_screen="ppe_type",
        )


class EditDuplicateItemPointsModal(discord.ui.Modal, title="Edit Duplicate Item Points"):
    point_reduction = discord.ui.TextInput(
        label="Point Reduction",
        placeholder="Example: 0.5 (set 0 to disable duplicates)",
        required=True,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
        source_screen: str = "landing",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.source_screen = source_screen

        raw_reduction = settings.get("duplicate_point_reduction", 0.5)
        try:
            parsed_reduction = float(raw_reduction)
        except (TypeError, ValueError):
            parsed_reduction = 0.5
        if parsed_reduction < 0:
            parsed_reduction = 0.5
        self.point_reduction.default = f"{parsed_reduction:.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            parsed = float(str(self.point_reduction.value).strip())
        except ValueError:
            await interaction.response.send_message("ERROR: Point Reduction must be a number.", ephemeral=True)
            return

        if parsed < 0:
            await interaction.response.send_message("ERROR: Point Reduction must be 0 or greater.", ephemeral=True)
            return

        confirm_text = (
            "⚠️ **Apply duplicate point reduction changes and recalculate all PPE characters?**\n"
            "Set `0` to disable duplicate item points.\n\n"
            f"Point Reduction: `{parsed:.2f}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_duplicate_item_point_reduction(
            interaction,
            duplicate_point_reduction=parsed,
        )

        await interaction.followup.send(
            "Updated duplicate item point reduction.\n"
            f"Point Reduction: {float(settings.get('duplicate_point_reduction', parsed)):.2f}x\n"
            "Set to 0 to disable duplicate item points.\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen=self.source_screen,
        )


class EditRarityModifiersModal(discord.ui.Modal, title="Edit Rarity Modifiers"):
    rarity_set = discord.ui.TextInput(
        label="Multipliers (C,U,R,L,D)",
        placeholder="Example: 1.00, 1.10, 1.25, 1.50, 2.00",
        required=False,
        max_length=80,
    )
    shiny = discord.ui.TextInput(
        label="Shiny Multiplier",
        placeholder="Example: 2.00",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        *,
        owner_id: int,
        settings: dict,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

        rarity_multipliers = (
            settings.get("rarity_multipliers", {})
            if isinstance(settings.get("rarity_multipliers"), dict)
            else {}
        )
        self.rarity_set.default = ", ".join(
            (
                f"{float(rarity_multipliers.get('common', 1.0)):.2f}",
                f"{float(rarity_multipliers.get('uncommon', 1.0)):.2f}",
                f"{float(rarity_multipliers.get('rare', 1.0)):.2f}",
                f"{float(rarity_multipliers.get('legendary', 1.0)):.2f}",
                f"{float(rarity_multipliers.get('divine', 2.0)):.2f}",
            )
        )
        self.shiny.default = f"{float(rarity_multipliers.get('shiny', 2.0)):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            rarity_set = _parse_optional_rarity_multiplier_set(self.rarity_set.value)
            shiny = _parse_optional_float(self.shiny.value, field_name="shiny")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if rarity_set is None and shiny is None:
            await interaction.response.send_message("ERROR: Provide at least one rarity multiplier to update.", ephemeral=True)
            return

        for value in ((list(rarity_set.values()) if rarity_set is not None else []) + ([shiny] if shiny is not None else [])):
            if value < 0:
                await interaction.response.send_message("ERROR: Rarity multipliers must be 0 or greater.", ephemeral=True)
                return

        common = rarity_set.get("common") if rarity_set is not None else None
        uncommon = rarity_set.get("uncommon") if rarity_set is not None else None
        rare = rarity_set.get("rare") if rarity_set is not None else None
        legendary = rarity_set.get("legendary") if rarity_set is not None else None
        divine = rarity_set.get("divine") if rarity_set is not None else None

        confirm_text = (
            "⚠️ **Apply rarity modifier changes and recalculate all PPE characters?**\n"
            "These multipliers affect item points by rarity.\n\n"
            f"Common, Unc, Rare, Leg, Divine: `{self.rarity_set.value or '(unchanged)'}`\n"
            f"Shiny: `{self.shiny.value or '(unchanged)'}`"
        )
        confirmed = await _confirm_points_update(
            interaction=interaction,
            owner_id=self.owner_id,
            confirmation_text=confirm_text,
        )
        if not confirmed:
            return

        settings, refresh_summary = await update_rarity_multipliers(
            interaction,
            common=common,
            uncommon=uncommon,
            rare=rare,
            legendary=legendary,
            divine=divine,
            shiny=shiny,
        )
        multipliers = settings.get("rarity_multipliers", {}) if isinstance(settings.get("rarity_multipliers"), dict) else {}

        await interaction.followup.send(
            "Updated rarity modifiers.\n"
            f"Common: {float(multipliers.get('common', 1.0)):.2f}x\n"
            f"Uncommon: {float(multipliers.get('uncommon', 1.0)):.2f}x\n"
            f"Rare: {float(multipliers.get('rare', 1.0)):.2f}x\n"
            f"Legendary: {float(multipliers.get('legendary', 1.0)):.2f}x\n"
            f"Divine: {float(multipliers.get('divine', 2.0)):.2f}x\n"
            f"Shiny: {float(multipliers.get('shiny', 2.0)):.2f}x\n"
            f"PPEs recalculated: {refresh_summary.ppes_processed}\n"
            f"PPE totals changed: {refresh_summary.ppes_updated}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            source_screen="landing",
        )
