"""Interactive views for /manageseason admin workflows."""

from __future__ import annotations

import discord

from dataclass import ROTMG_CLASSES

from menus.manageseason.common import (
    build_manageseason_home_embed,
    build_point_settings_embed,
    build_reset_completion_embed,
    build_reset_mode_embed,
)
from menus.manageseason.modals import EditClassPointSettingsModal, EditGlobalPointSettingsModal
from menus.manageseason.services import load_points_settings_for_menu, reset_season_data
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


def _has_discord_administrator_permission(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


class ManageSeasonHomeView(OwnerBoundView):
    """Top-level /manageseason view with reset + point-settings navigation."""

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

        view = ResetSeasonModeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Point Settings", style=discord.ButtonStyle.primary, row=0)
    async def manage_point_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ResetSeasonModeView(OwnerBoundView):
    """Reset flow mode picker that branches by RealmShark link handling strategy."""

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id

    def current_embed(self) -> discord.Embed:
        return build_reset_mode_embed()

    async def _confirm_and_execute(self, interaction: discord.Interaction, *, clear_realmshark_links: bool) -> None:
        mode_text = (
            "unlink all RealmShark links and remove all mappings"
            if clear_realmshark_links
            else "keep RealmShark links and convert PPE mappings to seasonal mappings"
        )

        confirm_view = ConfirmCancelView(
            owner_id=self.owner_id,
            timeout=60,
            confirm_label="Confirm Reset",
            cancel_label="Cancel",
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.secondary,
            owner_error="This confirmation belongs to another user.",
        )

        await interaction.response.send_message(
            "WARNING: **Are you sure you want to reset the season?**\n"
            "This will clear all PPE data, season loot, quest progress, and teams.\n"
            f"Mode selected: **{mode_text}**.",
            view=confirm_view,
            ephemeral=True,
        )

        await confirm_view.wait()
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        if not confirm_view.confirmed:
            await interaction.followup.send("Season reset cancelled.", ephemeral=True)
            return

        await interaction.followup.send("Running season reset. This may take a few seconds...", ephemeral=True)

        try:
            summary = await reset_season_data(interaction, clear_realmshark_links=clear_realmshark_links)
        except (ValueError, KeyError) as exc:
            await interaction.followup.send(f"ERROR: {exc}", ephemeral=True)
            return
        except Exception as exc:
            await interaction.followup.send(f"ERROR: Unexpected reset failure: {exc}", ephemeral=True)
            return

        embed = build_reset_completion_embed(summary, actor_name=interaction.user.display_name)
        await interaction.followup.send(embed=embed, ephemeral=False)

        if interaction.message is not None:
            home_view = ManageSeasonHomeView(owner_id=self.owner_id)
            try:
                await interaction.message.edit(embed=home_view.current_embed(), view=home_view)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Keep RealmShark Links", style=discord.ButtonStyle.success, row=0)
    async def keep_links(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._confirm_and_execute(interaction, clear_realmshark_links=False)

    @discord.ui.button(label="Unlink RealmShark Links", style=discord.ButtonStyle.danger, row=0)
    async def clear_links(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._confirm_and_execute(interaction, clear_realmshark_links=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


class _PointSettingsClassSelect(discord.ui.Select):
    """Class selector used by ManagePointSettingsView for targeted class overrides."""

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
            row=1,
        )
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This selector belongs to another user.", ephemeral=True)
            return

        view = self.view
        if not isinstance(view, ManagePointSettingsView):
            await interaction.response.send_message("Invalid selector state.", ephemeral=True)
            return

        view.selected_class = self.values[0]
        for option in self.options:
            option.default = option.value == view.selected_class

        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManagePointSettingsView(OwnerBoundView):
    """Subview for viewing and editing global/class point modifiers."""

    def __init__(self, *, owner_id: int, settings: dict, selected_class: str | None = None) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self.selected_class = selected_class
        self.add_item(_PointSettingsClassSelect(owner_id=self.owner_id, selected_class=self.selected_class))

    def current_embed(self) -> discord.Embed:
        embed = build_point_settings_embed(self.settings)
        target = self.selected_class if self.selected_class is not None else "No class selected yet."
        embed.add_field(name="Class Override Target", value=target, inline=False)
        return embed

    @discord.ui.button(label="Edit Global Modifiers", style=discord.ButtonStyle.primary, row=0)
    async def edit_global(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        await interaction.response.send_modal(
            EditGlobalPointSettingsModal(
                owner_id=self.owner_id,
                settings=self.settings,
                source_message=interaction.message,
                selected_class=self.selected_class,
            )
        )

    @discord.ui.button(label="Edit Class Override", style=discord.ButtonStyle.primary, row=0)
    async def edit_class(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.selected_class is None:
            await interaction.response.send_message("ERROR: Select a class from the dropdown first.", ephemeral=True)
            return

        self.settings = await load_points_settings_for_menu(interaction)
        existing_override = self.settings.get("class_overrides", {}).get(self.selected_class, {})
        await interaction.response.send_modal(
            EditClassPointSettingsModal(
                owner_id=self.owner_id,
                class_name=self.selected_class,
                source_message=interaction.message,
                existing_override=existing_override if isinstance(existing_override, dict) else None,
            )
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)
