"""Home submenu views for /managequests."""

from __future__ import annotations

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

    def current_embed(self) -> discord.Embed:
        return build_managequests_home_embed(self.settings)

    @discord.ui.button(label="Reset All Quests", style=discord.ButtonStyle.danger, row=0)
    async def reset_all(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_reset_all_quests_confirmation(interaction, owner_id=self.owner_id)

    @discord.ui.button(label="Edit Quest Settings", style=discord.ButtonStyle.success, row=0)
    async def edit_settings(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.settings = await load_managequests_settings(interaction)
        await interaction.response.send_modal(
            EditQuestSettingsModal(owner_id=self.owner_id, settings=self.settings, source_message=interaction.message)
        )

    @discord.ui.button(label="Set Global Quests", style=discord.ButtonStyle.success, row=0)
    async def set_global_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managequests.submenus.global_quests.views import GlobalQuestsView

        settings = await load_managequests_settings(interaction)
        view = GlobalQuestsView(owner_id=self.owner_id, settings=settings)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Manage Player's Quests", style=discord.ButtonStyle.success, row=1)
    async def manage_player_quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.managequests.submenus.player_reset.views import ManagePlayerQuestsPromptModal

        await interaction.response.send_modal(
            ManagePlayerQuestsPromptModal(owner_id=self.owner_id, source_message=interaction.message)
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/managequests` menu.", embed=None, view=None)


__all__ = ["ManageQuestsHomeView"]
