"""Home view for /manageteams admin menu."""

from __future__ import annotations

import discord

from menus.leaderboard.common import (
    LEADERBOARD_PAGE_SIZE,
    build_leaderboard_embeds,
    build_ranked_entry_lines,
)
from menus.menu_utils import OwnerBoundView
from menus.manageteams.modals import CreateTeamModal
from utils.player_records import load_teams
from utils.team_contest_scoring import format_points_breakdown, load_team_contest_scoring
from utils.team_manager import team_manager


class ManageTeamsHomeView(OwnerBoundView):
    """Home view with pagination, create team, and leaderboard access."""

    def __init__(self, *, owner_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.pages = pages
        self.index = 0

        if len(self.pages) <= 1:
            self.remove_item(self.prev_page)
            self.remove_item(self.next_page)

    def current_embed(self) -> discord.Embed:
        return self.pages[self.index]

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Create New Team", style=discord.ButtonStyle.success, row=1)
    async def create_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(CreateTeamModal(owner_id=self.owner_id))

    @discord.ui.button(label="Manage Team", style=discord.ButtonStyle.success, row=1)
    async def manage_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.submenus.team_picker.views import TeamPickerView

        teams = await load_teams(interaction)
        ordered_names = sorted(teams.keys(), key=lambda name: name.lower())
        picker = TeamPickerView(owner_id=self.owner_id, team_names=ordered_names)
        await interaction.response.edit_message(embed=picker.current_embed(), view=picker)

    @discord.ui.button(label="Team Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def team_leaderboard(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.submenus.leaderboard.views import LeaderboardPreviewView

        data = await team_manager.get_team_leaderboard_data(interaction)
        if not data:
            await interaction.response.send_message("No teams available yet.", ephemeral=True)
            return

        scoring = await load_team_contest_scoring(interaction)
        rows: list[str] = []
        for team_name, _leader_id, ppe_points, quest_points, total_points, member_count in data:
            breakdown = format_points_breakdown(
                ppe_points=ppe_points,
                quest_points=quest_points,
                total_points=total_points,
                include_quest_points=scoring.include_quest_points,
            )
            rows.append(f"**{team_name}**: {breakdown} pts ({member_count} members)")
        embeds = build_leaderboard_embeds(
            title="Team Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            per_page=LEADERBOARD_PAGE_SIZE,
        )
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
            return

        view = LeaderboardPreviewView(owner_id=self.owner_id, embeds=embeds)
        await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=2)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Closed `/manageteams` menu.", embed=None, view=None)
