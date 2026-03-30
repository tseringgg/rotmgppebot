"""Team picker view for /manageteams admin menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.manageteams.modals import TeamNameLookupModal, TeamNameSelect


class TeamPickerView(OwnerBoundView):
    """Dropdown to pick a team from list, or lookup by name."""

    def __init__(self, *, owner_id: int, team_names: list[str]) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_names = team_names
        self.use_lookup_only = len(self.team_names) > 20

        if self.team_names and not self.use_lookup_only:
            self.add_item(TeamNameSelect(team_names=self.team_names))

    def current_embed(self) -> discord.Embed:
        if not self.team_names:
            description = "No teams exist yet. Create one from the home page first."
        elif self.use_lookup_only:
            description = (
                "This server has many teams, so quick-lookup is enabled.\n"
                "Use **Find Team** to jump to any team by name."
            )
        else:
            description = "Select a team from the dropdown, or use **Find Team** to search by name."

        return discord.Embed(
            title="Manage Team",
            description=description,
            color=discord.Color.teal(),
        )

    @discord.ui.button(label="Find Team", style=discord.ButtonStyle.primary, row=1)
    async def find_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.team_names:
            await interaction.response.send_message("❌ No teams exist yet.", ephemeral=True)
            return
        await interaction.response.send_modal(TeamNameLookupModal(owner_id=self.owner_id, team_names=self.team_names))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)
