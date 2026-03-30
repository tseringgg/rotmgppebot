"""Team detail views for /manageteams admin menu."""

from __future__ import annotations

import discord

from dataclass import TeamData
from menus.leaderboard.common import LEADERBOARD_PAGE_SIZE, build_ranked_entry_lines
from menus.menu_utils import OwnerBoundView
from menus.manageteams.common import resolve_team_name
from menus.manageteams.modals import (
    AddMemberModal,
    RemoveMembersModal,
    RenameTeamModal,
    SetLeaderModal,
)
from utils.player_records import load_player_records, load_teams
from utils.team_contest_scoring import format_points_breakdown


class ManageSingleTeamView(OwnerBoundView):
    """View for managing a single team with all member actions."""

    def __init__(
        self,
        *,
        owner_id: int,
        team_name: str,
        team: TeamData,
        member_rows: list[tuple[int, str, float, float, float, str]],
        include_quest_points: bool,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_name = team_name
        self.team = team
        self.member_rows = member_rows
        self.include_quest_points = include_quest_points

    def current_embed(self) -> discord.Embed:
        total_points = sum(member[4] for member in self.member_rows)
        leader_label = f"<@{self.team.leader_id}>" if self.team.leader_id else "Unassigned"
        scoring_mode = "PPE + Quest" if self.include_quest_points else "PPE Only"

        embed = discord.Embed(
            title=f"Manage Team - {self.team_name}",
            description=(
                f"Leader: {leader_label}\n"
                f"Members: **{len(self.member_rows)}**\n"
                f"Scoring Mode: **{scoring_mode}**\n"
                f"Team Total Contribution: **{total_points:.1f}** pts"
            ),
            color=discord.Color.blurple(),
        )

        if not self.member_rows:
            embed.add_field(name="Members", value="No members yet.", inline=False)
            return embed

        lines: list[str] = []
        for rank, (_member_id, member_name, ppe_points, quest_points, contribution, best_class) in enumerate(self.member_rows, start=1):
            breakdown = format_points_breakdown(
                ppe_points=ppe_points,
                quest_points=quest_points,
                total_points=contribution,
                include_quest_points=self.include_quest_points,
            )
            lines.append(
                f"{rank}. **{member_name}** ({best_class}): {breakdown}"
            )

        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."
        embed.add_field(name="Member Contributions", value=text, inline=False)
        return embed

    def _build_team_info_embeds(self) -> list[discord.Embed]:
        leader_label = f"<@{self.team.leader_id}>" if self.team.leader_id else "Unassigned"
        total_ppe = sum(row[2] for row in self.member_rows)
        total_quest = sum(row[3] for row in self.member_rows)
        total_points = sum(row[4] for row in self.member_rows)
        total_label = "PPE + Quest Points" if self.include_quest_points else "PPE Points"
        total_breakdown = format_points_breakdown(
            ppe_points=total_ppe,
            quest_points=total_quest,
            total_points=total_points,
            include_quest_points=self.include_quest_points,
        )

        if not self.member_rows:
            embed = discord.Embed(
                title=f"Team Info - {self.team_name}",
                description=f"Leader: {leader_label}",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Members", value="0", inline=True)
            embed.add_field(name=total_label, value=total_breakdown, inline=True)
            embed.add_field(name="Rankings", value="This team has no members yet.", inline=False)
            return [embed]

        lines: list[str] = []
        for rank, (_member_id, member_name, ppe_points, quest_points, contribution, best_class) in enumerate(
            self.member_rows,
            start=1,
        ):
            breakdown = format_points_breakdown(
                ppe_points=ppe_points,
                quest_points=quest_points,
                total_points=contribution,
                include_quest_points=self.include_quest_points,
            )
            lines.append(f"{rank}. {member_name}: {breakdown} pts ({best_class})")

        pages = [lines[index:index + LEADERBOARD_PAGE_SIZE] for index in range(0, len(lines), LEADERBOARD_PAGE_SIZE)]
        embeds: list[discord.Embed] = []
        page_count = len(pages)

        for page_number, page_lines in enumerate(pages, start=1):
            embed = discord.Embed(
                title=f"Team Info - {self.team_name}",
                description=f"Leader: {leader_label}",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Members", value=str(len(self.member_rows)), inline=True)
            embed.add_field(name=total_label, value=total_breakdown, inline=True)

            ranking_value = "\n".join(page_lines)
            if len(ranking_value) > 1024:
                ranking_value = ranking_value[:1000].rstrip() + "\n..."
            embed.add_field(name="Rankings", value=ranking_value, inline=False)

            if page_count > 1:
                embed.set_footer(text=f"Page {page_number}/{page_count}")
            embeds.append(embed)

        return embeds

    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.success, row=0)
    async def add_member(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        records = await load_player_records(interaction)
        teams = await load_teams(interaction)
        actual_name = resolve_team_name(teams, self.team_name)
        if not actual_name:
            await interaction.response.send_message(f"❌ Team `{self.team_name}` no longer exists.", ephemeral=True)
            return
        team = teams[actual_name]

        eligible: list[discord.Member] = []
        if interaction.guild:
            for member in interaction.guild.members:
                if member.bot:
                    continue
                player_data = records.get(member.id)
                if not player_data or not player_data.is_member:
                    continue
                if player_data.team_name:
                    continue
                if member.id in team.members:
                    continue
                eligible.append(member)

        eligible.sort(key=lambda member: member.display_name.lower())
        if not eligible:
            await interaction.response.send_message("❌ No eligible PPE members are available to add.", ephemeral=True)
            return

        await interaction.response.send_modal(
            AddMemberModal(owner_id=self.owner_id, team_name=actual_name, eligible_members=eligible)
        )

    @discord.ui.button(label="Set Leader", style=discord.ButtonStyle.success, row=0)
    async def set_leader(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.member_rows:
            await interaction.response.send_message("❌ This team has no members. Add one before setting leader.", ephemeral=True)
            return
        await interaction.response.send_modal(
            SetLeaderModal(owner_id=self.owner_id, team_name=self.team_name, member_rows=self.member_rows)
        )

    @discord.ui.button(label="Rename Team", style=discord.ButtonStyle.success, row=0)
    async def rename_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RenameTeamModal(owner_id=self.owner_id, team_name=self.team_name))

    @discord.ui.button(label="Team Info", style=discord.ButtonStyle.primary, row=0)
    async def team_info(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embeds = self._build_team_info_embeds()
        view = TeamInfoPreviewView(owner_id=self.owner_id, embeds=embeds, team_name=self.team_name)
        await interaction.response.edit_message(embed=view.embeds[0], view=view)

    @discord.ui.button(label="Remove Members", style=discord.ButtonStyle.danger, row=1)
    async def remove_selected(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.member_rows:
            await interaction.response.send_message("❌ This team has no members to remove.", ephemeral=True)
            return
        await interaction.response.send_modal(
            RemoveMembersModal(owner_id=self.owner_id, team_name=self.team_name, member_rows=self.member_rows)
        )

    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.danger, row=1)
    async def delete_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.submenus.confirmations.views import TeamDeleteConfirmView

        view = TeamDeleteConfirmView(owner_id=self.owner_id, team_name=self.team_name)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)


class TeamInfoPreviewView(OwnerBoundView):
    """Paginated display of team info with back button."""

    def __init__(self, *, owner_id: int, embeds: list[discord.Embed], team_name: str) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.embeds = embeds
        self.team_name = team_name
        self.index = 0

        if len(self.embeds) <= 1:
            self.remove_item(self.prev_page)
            self.remove_item(self.next_page)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
