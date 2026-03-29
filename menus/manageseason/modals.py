"""Modal workflows for editing point settings from /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.services import (
    load_points_settings_for_menu,
    update_class_point_override,
    update_global_point_modifiers,
)


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


async def _refresh_point_settings_message(
    *,
    interaction: discord.Interaction,
    owner_id: int,
    source_message: discord.Message | None,
    settings: dict | None = None,
    selected_class: str | None = None,
) -> None:
    if source_message is None:
        return

    from menus.manageseason.views import ManagePointSettingsView

    refreshed = settings if settings is not None else await load_points_settings_for_menu(interaction)
    view = ManagePointSettingsView(owner_id=owner_id, settings=refreshed, selected_class=selected_class)

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
        selected_class: str | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message
        self.selected_class = selected_class

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

        settings = await update_global_point_modifiers(
            interaction,
            loot_percent=loot_percent,
            bonus_percent=bonus_percent,
            penalty_percent=penalty_percent,
            total_percent=total_percent,
        )

        global_settings = settings.get("global", {})
        await interaction.response.send_message(
            "Updated global point modifiers.\n"
            f"Loot: {float(global_settings.get('loot_percent', 0.0)):.2f}%\n"
            f"Bonus: {float(global_settings.get('bonus_percent', 0.0)):.2f}%\n"
            f"Penalty: {float(global_settings.get('penalty_percent', 0.0)):.2f}%\n"
            f"Total: {float(global_settings.get('total_percent', 0.0)):.2f}%",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            selected_class=self.selected_class,
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
    ) -> None:
        super().__init__(title=f"Edit Class Override - {class_name}", timeout=300)
        self.owner_id = owner_id
        self.class_name = class_name
        self.source_message = source_message

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

        settings, class_override = await update_class_point_override(
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
        await interaction.response.send_message(
            f"Updated class override for {self.class_name}.\n"
            f"Loot: {float(class_override.get('loot_percent', 0.0)):.2f}%\n"
            f"Bonus: {float(class_override.get('bonus_percent', 0.0)):.2f}%\n"
            f"Penalty: {float(class_override.get('penalty_percent', 0.0)):.2f}%\n"
            f"Total: {float(class_override.get('total_percent', 0.0)):.2f}%\n"
            f"Minimum total: {min_text}",
            ephemeral=True,
        )

        await _refresh_point_settings_message(
            interaction=interaction,
            owner_id=self.owner_id,
            source_message=self.source_message,
            settings=settings,
            selected_class=self.class_name,
        )
