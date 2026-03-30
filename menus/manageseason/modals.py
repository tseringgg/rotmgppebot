"""Modal workflows for editing point settings from /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.services import (
    load_points_settings_for_menu,
    update_class_point_override,
    update_global_point_modifiers,
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
        ManagePointSettingsView,
    )

    refreshed = settings if settings is not None else await load_points_settings_for_menu(interaction)
    if source_screen == "global":
        view = ManageGlobalPointSettingsView(owner_id=owner_id, settings=refreshed)
    elif source_screen == "class":
        view = ManageClassPointSettingsView(owner_id=owner_id, settings=refreshed, selected_class=selected_class)
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
