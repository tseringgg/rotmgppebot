"""Modal workflows for editing point settings from /manageseason."""

from __future__ import annotations

import discord

from utils.ppe_types import ppe_type_label
from menus.manageseason.services import (
    load_character_settings_for_menu,
    load_points_settings_for_menu,
    update_class_point_override,
    update_duplicate_item_point_reduction,
    update_global_point_modifiers,
    update_penalty_base_rates,
    update_pet_point_modifiers,
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
        ManageGlobalPointSettingsView,
        ManagePpeTypePointSettingsView,
        ManagePointSettingsView,
    )

    refreshed = settings if settings is not None else await load_points_settings_for_menu(interaction)
    if source_screen == "global":
        view = ManageGlobalPointSettingsView(owner_id=owner_id, settings=refreshed)
    elif source_screen == "class":
        view = ManageClassPointSettingsView(owner_id=owner_id, settings=refreshed, selected_class=selected_class)
    elif source_screen == "ppe_type":
        character_settings = await load_character_settings_for_menu(interaction)
        view = ManagePpeTypePointSettingsView(owner_id=owner_id, character_settings=character_settings)
    else:
        view = ManagePointSettingsView(owner_id=owner_id, settings=refreshed)

    try:
        await source_message.edit(embed=view.current_embed(), view=view)
    except discord.HTTPException:
        pass


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
        super().__init__(title=f"Edit PPE Type Points - {ppe_type_label(ppe_type)}", timeout=300)
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
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

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
            source_screen="landing",
        )


class EditRarityModifiersModal(discord.ui.Modal, title="Edit Rarity Modifiers"):
    common = discord.ui.TextInput(
        label="Common Multiplier",
        placeholder="Example: 1.0",
        required=False,
        max_length=20,
    )
    uncommon = discord.ui.TextInput(
        label="Uncommon Multiplier",
        placeholder="Example: 1.0",
        required=False,
        max_length=20,
    )
    rare = discord.ui.TextInput(
        label="Rare Multiplier",
        placeholder="Example: 1.0",
        required=False,
        max_length=20,
    )
    legendary = discord.ui.TextInput(
        label="Legendary Multiplier",
        placeholder="Example: 1.0",
        required=False,
        max_length=20,
    )
    divine = discord.ui.TextInput(
        label="Divine Multiplier",
        placeholder="Example: 2.0",
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
        self.common.default = f"{float(rarity_multipliers.get('common', 1.0)):.2f}"
        self.uncommon.default = f"{float(rarity_multipliers.get('uncommon', 1.0)):.2f}"
        self.rare.default = f"{float(rarity_multipliers.get('rare', 1.0)):.2f}"
        self.legendary.default = f"{float(rarity_multipliers.get('legendary', 1.0)):.2f}"
        self.divine.default = f"{float(rarity_multipliers.get('divine', 2.0)):.2f}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        try:
            common = _parse_optional_float(self.common.value, field_name="common")
            uncommon = _parse_optional_float(self.uncommon.value, field_name="uncommon")
            rare = _parse_optional_float(self.rare.value, field_name="rare")
            legendary = _parse_optional_float(self.legendary.value, field_name="legendary")
            divine = _parse_optional_float(self.divine.value, field_name="divine")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if all(value is None for value in (common, uncommon, rare, legendary, divine)):
            await interaction.response.send_message("ERROR: Provide at least one rarity multiplier to update.", ephemeral=True)
            return

        for value in (common, uncommon, rare, legendary, divine):
            if value is not None and value < 0:
                await interaction.response.send_message("ERROR: Rarity multipliers must be 0 or greater.", ephemeral=True)
                return

        confirm_text = (
            "⚠️ **Apply rarity modifier changes and recalculate all PPE characters?**\n"
            "These multipliers affect item points by rarity.\n\n"
            f"Common: `{self.common.value or '(unchanged)'}`\n"
            f"Uncommon: `{self.uncommon.value or '(unchanged)'}`\n"
            f"Rare: `{self.rare.value or '(unchanged)'}`\n"
            f"Legendary: `{self.legendary.value or '(unchanged)'}`\n"
            f"Divine: `{self.divine.value or '(unchanged)'}`"
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
        )
        multipliers = settings.get("rarity_multipliers", {}) if isinstance(settings.get("rarity_multipliers"), dict) else {}

        await interaction.followup.send(
            "Updated rarity modifiers.\n"
            f"Common: {float(multipliers.get('common', 1.0)):.2f}x\n"
            f"Uncommon: {float(multipliers.get('uncommon', 1.0)):.2f}x\n"
            f"Rare: {float(multipliers.get('rare', 1.0)):.2f}x\n"
            f"Legendary: {float(multipliers.get('legendary', 1.0)):.2f}x\n"
            f"Divine: {float(multipliers.get('divine', 2.0)):.2f}x\n"
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
