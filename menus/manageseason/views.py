"""Interactive views for /manageseason admin workflows."""

from __future__ import annotations

import discord

from dataclass import ROTMG_CLASSES
from menus.manageseason.common import (
    build_class_modifier_settings_embed,
    build_global_modifier_settings_embed,
    build_leaderboard_manager_embed,
    build_manage_contests_embed,
    build_manageseason_home_embed,
    build_point_settings_embed,
    build_reset_completion_embed,
    build_reset_mode_embed,
    build_set_contest_type_embed,
)
from menus.manageseason.modals import EditClassPointSettingsModal, EditGlobalPointSettingsModal
from menus.manageseason.services import (
    load_contest_settings_for_menu,
    load_points_settings_for_menu,
    reset_season_data,
    update_default_contest_leaderboard,
    update_team_contest_quest_points_setting,
)
from menus.menu_utils import ConfirmCancelView, OwnerBoundView


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

        view = ResetSeasonModeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Point Settings", style=discord.ButtonStyle.primary, row=0)
    async def manage_point_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_points_settings_for_menu(interaction)
        view = ManagePointSettingsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Contests", style=discord.ButtonStyle.primary, row=0)
    async def manage_contests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        view = ManageContestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class ManageContestsHomeView(OwnerBoundView):
    """Landing view for contest leaderboard defaults and contest scoring settings."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_manage_contests_embed(self.settings)

    @discord.ui.button(label="Set Contest Type", style=discord.ButtonStyle.primary, row=0)
    async def set_contest_type(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_contest_settings_for_menu(interaction)
        view = SetContestTypeView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Leaderboards", style=discord.ButtonStyle.primary, row=0)
    async def manage_leaderboards(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_contest_settings_for_menu(interaction)
        view = LeaderboardManagerView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        home_view = ManageSeasonHomeView(owner_id=self.owner_id)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)


class SetContestTypeView(OwnerBoundView):
    """Button-based default contest leaderboard selection view."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._sync_button_state()

    def _sync_button_state(self) -> None:
        current_default = self.settings.get("default_contest_leaderboard")

        option_map: dict[str, discord.ui.Button] = {
            "ppe": self.set_ppe,
            "quest": self.set_quest,
            "season": self.set_season,
            "team": self.set_team,
        }

        for option_id, button in option_map.items():
            is_selected = current_default == option_id
            button.style = discord.ButtonStyle.success if is_selected else discord.ButtonStyle.primary

        self.clear_default.style = (
            discord.ButtonStyle.secondary if current_default is None else discord.ButtonStyle.danger
        )

    def current_embed(self) -> discord.Embed:
        return build_set_contest_type_embed(self.settings)

    async def _set_default(self, interaction: discord.Interaction, *, default_leaderboard: str | None) -> None:
        self.settings = await update_default_contest_leaderboard(
            interaction,
            default_leaderboard=default_leaderboard,
        )
        self._sync_button_state()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="PPE", style=discord.ButtonStyle.primary, row=0)
    async def set_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="ppe")

    @discord.ui.button(label="Quest", style=discord.ButtonStyle.primary, row=0)
    async def set_quest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="quest")

    @discord.ui.button(label="Season Loot", style=discord.ButtonStyle.primary, row=0)
    async def set_season(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="season")

    @discord.ui.button(label="Team", style=discord.ButtonStyle.primary, row=0)
    async def set_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="team")

    @discord.ui.button(label="Clear Default", style=discord.ButtonStyle.danger, row=1)
    async def clear_default(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard=None)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        view = ManageContestsHomeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class LeaderboardManagerView(OwnerBoundView):
    """Contest leaderboard scoring manager."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._sync_toggle_button()

    def _sync_toggle_button(self) -> None:
        enabled = bool(self.settings.get("team_contest_include_quest_points", False))
        if enabled:
            self.toggle_team_quest_points.label = "Disable Team Quest Points"
            self.toggle_team_quest_points.style = discord.ButtonStyle.danger
        else:
            self.toggle_team_quest_points.label = "Enable Team Quest Points"
            self.toggle_team_quest_points.style = discord.ButtonStyle.success

    def current_embed(self) -> discord.Embed:
        return build_leaderboard_manager_embed(self.settings)

    @discord.ui.button(label="Enable Team Quest Points", style=discord.ButtonStyle.success, row=0)
    async def toggle_team_quest_points(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        currently_enabled = bool(self.settings.get("team_contest_include_quest_points", False))
        self.settings = await update_team_contest_quest_points_setting(
            interaction,
            enabled=not currently_enabled,
        )
        self._sync_toggle_button()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        settings = await load_contest_settings_for_menu(interaction)
        view = ManageContestsHomeView(owner_id=self.owner_id, settings=settings)
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


class ManagePointSettingsView(OwnerBoundView):
    """Landing view for point modifier workflows."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings

    def current_embed(self) -> discord.Embed:
        return build_point_settings_embed(self.settings)

    @discord.ui.button(label="Edit Global Modifiers", style=discord.ButtonStyle.primary, row=0)
    async def edit_global(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageGlobalPointSettingsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Edit Class Modifiers", style=discord.ButtonStyle.primary, row=0)
    async def edit_class(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_points_settings_for_menu(interaction)
        view = ManageClassPointSettingsView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
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

    @discord.ui.button(label="Edit Global Modifiers", style=discord.ButtonStyle.primary, row=0)
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

    @discord.ui.button(label="Edit Selected Class", style=discord.ButtonStyle.primary, row=1)
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
