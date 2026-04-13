"""Home submenu views for /managequests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from menus.managequests.common import build_managequests_home_embed, load_managequests_settings
from menus.managequests.modals import EditQuestSettingsModal
from menus.managequests.reset_actions import open_reset_all_quests_confirmation
from menus.menu_utils import OwnerBoundView


class ManageQuestsHomeView(OwnerBoundView):
    """Top-level /managequests admin controls."""

    def __init__(self, *, owner_id: int, settings: dict) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.settings = settings
        self._rebuild_controls()

    def current_embed(self) -> discord.Embed:
        return build_managequests_home_embed(self.settings)

    def _add_button(
        self,
        *,
        label: str,
        style: discord.ButtonStyle,
        row: int,
        handler: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        button = discord.ui.Button(label=label, style=style, row=row)

        async def _callback(interaction: discord.Interaction) -> None:
            await handler(interaction)

        button.callback = _callback
        self.add_item(button)

    def _rebuild_controls(self) -> None:
        self.clear_items()
        team_mode_enabled = bool(self.settings.get("enable_team_quests", False)) and not bool(
            self.settings.get("use_global_quests", False)
        )

        self._add_button(label="Reset All Quests", style=discord.ButtonStyle.danger, row=0, handler=self._reset_all)
        self._add_button(label="Edit Quest Settings", style=discord.ButtonStyle.success, row=0, handler=self._edit_settings)
        self._add_button(label="Manage Quest Mode", style=discord.ButtonStyle.success, row=0, handler=self._manage_quest_mode)

        self._add_button(
            label="Manage Player's Quests",
            style=discord.ButtonStyle.success,
            row=1,
            handler=self._manage_player_quests,
        )
        if team_mode_enabled:
            self._add_button(
                label="Reset Team's Quests",
                style=discord.ButtonStyle.danger,
                row=1,
                handler=self._reset_team_quests,
            )
        self._add_button(label="Close", style=discord.ButtonStyle.secondary, row=2, handler=self._close)

    async def _reset_all(self, interaction: discord.Interaction) -> None:
        await open_reset_all_quests_confirmation(interaction, owner_id=self.owner_id)

    async def _edit_settings(self, interaction: discord.Interaction) -> None:
        self.settings = await load_managequests_settings(interaction)
        await interaction.response.send_modal(
            EditQuestSettingsModal(owner_id=self.owner_id, settings=self.settings, source_message=interaction.message)
        )

    async def _manage_quest_mode(self, interaction: discord.Interaction) -> None:
        from menus.managequests.submenus.quest_mode.views import QuestModeView

        settings = await load_managequests_settings(interaction)
        view = QuestModeView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    async def _manage_player_quests(self, interaction: discord.Interaction) -> None:
        from menus.managequests.submenus.player_reset.views import ManagePlayerQuestsPromptModal

        await interaction.response.send_modal(
            ManagePlayerQuestsPromptModal(owner_id=self.owner_id, source_message=interaction.message)
        )

    async def _reset_team_quests(self, interaction: discord.Interaction) -> None:
        from menus.managequests.submenus.player_reset.views import ManageTeamQuestsSelectView
        from utils.player_records import load_teams

        teams = await load_teams(interaction)
        view = ManageTeamQuestsSelectView(owner_id=self.owner_id, team_names=list(teams.keys()))
        await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)

    async def _close(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)


__all__ = ["ManageQuestsHomeView"]
