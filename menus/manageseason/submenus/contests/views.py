"""Contests submenu views for /manageseason."""

from __future__ import annotations

import discord

from menus.manageseason.common import (
    build_leaderboard_manager_embed,
    build_manage_contests_embed,
    build_set_contest_type_embed,
)
from menus.manageseason.services import (
    create_join_contest_embed,
    delete_join_contest_embed,
    load_contest_settings_for_menu,
    update_default_contest_leaderboard,
    update_team_contest_quest_points_setting,
)
from menus.menu_utils import OwnerBoundView
from menus.menu_utils.lookup_parsing import parse_channel_id


class CreateJoinContestEmbedModal(discord.ui.Modal, title="Create Join Contest Embed"):
    """Prompt admin for target channel where join-role embed should be posted."""

    channel_input = discord.ui.TextInput(
        label="Channel",
        placeholder="Use a channel mention like #general or a channel ID",
        required=True,
        max_length=64,
    )

    def __init__(self, *, owner_id: int, source_message: discord.Message | None) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.source_message = source_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        channel_id = parse_channel_id(self.channel_input.value)
        if channel_id is None:
            await interaction.response.send_message(
                "ERROR: Provide a valid channel mention or numeric channel ID.",
                ephemeral=True,
            )
            return

        try:
            result = await create_join_contest_embed(interaction, channel_id=channel_id)
        except ValueError as exc:
            await interaction.response.send_message(f"ERROR: {exc}", ephemeral=True)
            return

        configured_channel_id = int(result["channel_id"])
        configured_message_id = int(result["message_id"])
        await interaction.response.send_message(
            "✅ Join contest embed created.\n"
            f"Channel: <#{configured_channel_id}>\n"
            f"Message ID: `{configured_message_id}`",
            ephemeral=True,
        )

        if self.source_message is not None:
            settings = await load_contest_settings_for_menu(interaction)
            refreshed_view = ManageContestsHomeView(owner_id=self.owner_id, settings=settings)
            try:
                await self.source_message.edit(embed=refreshed_view.current_embed(), view=refreshed_view)
            except discord.HTTPException:
                pass


class ManageContestsHomeView(OwnerBoundView):
    """Landing view for contest leaderboard defaults and contest scoring settings."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._sync_join_embed_button()

    def _sync_join_embed_button(self) -> None:
        message_id = int(self.settings.get("join_contest_message_id", 0) or 0)
        if message_id > 0:
            self.join_contest_embed.label = "Delete Join Embed"
            self.join_contest_embed.style = discord.ButtonStyle.danger
        else:
            self.join_contest_embed.label = "Create Join Embed"
            self.join_contest_embed.style = discord.ButtonStyle.success

    def current_embed(self) -> discord.Embed:
        return build_manage_contests_embed(self.settings)

    @discord.ui.button(label="Set Contest Type", style=discord.ButtonStyle.success, row=0)
    async def set_contest_type(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_contest_settings_for_menu(interaction)
        view = SetContestTypeView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Leaderboards", style=discord.ButtonStyle.success, row=0)
    async def manage_leaderboards(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_contest_settings_for_menu(interaction)
        view = LeaderboardManagerView(owner_id=self.owner_id, settings=self.settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Create Join Embed", style=discord.ButtonStyle.success, row=1)
    async def join_contest_embed(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_contest_settings_for_menu(interaction)
        message_id = int(self.settings.get("join_contest_message_id", 0) or 0)

        if message_id > 0:
            result = await delete_join_contest_embed(interaction)
            self.settings = dict(result.get("settings", {}))
            self._sync_join_embed_button()
            await interaction.response.edit_message(embed=self.current_embed(), view=self)
            await interaction.followup.send("✅ Join contest embed configuration cleared.", ephemeral=True)
            return

        modal = CreateJoinContestEmbedModal(owner_id=self.owner_id, source_message=interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageseason.submenus.home.views import ManageSeasonHomeView

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
            button.style = discord.ButtonStyle.success if is_selected else discord.ButtonStyle.success

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

    @discord.ui.button(label="PPE", style=discord.ButtonStyle.success, row=0)
    async def set_ppe(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="ppe")

    @discord.ui.button(label="Quest", style=discord.ButtonStyle.success, row=0)
    async def set_quest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="quest")

    @discord.ui.button(label="Season Loot", style=discord.ButtonStyle.success, row=0)
    async def set_season(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._set_default(interaction, default_leaderboard="season")

    @discord.ui.button(label="Team", style=discord.ButtonStyle.success, row=0)
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


__all__ = ["ManageContestsHomeView", "SetContestTypeView", "LeaderboardManagerView"]
