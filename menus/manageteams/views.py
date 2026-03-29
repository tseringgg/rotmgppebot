from __future__ import annotations

import discord

from dataclass import TeamData
from menus.leaderboard.common import (
    LEADERBOARD_PAGE_SIZE,
    build_leaderboard_embeds,
    build_ranked_entry_lines,
)
from menus.menu_utils import OwnerBoundView
from menus.manageteams.common import resolve_team_name
from menus.manageteams.modals import (
    AddMemberModal,
    CreateTeamModal,
    RemoveMembersModal,
    RenameTeamModal,
    SetLeaderModal,
    TeamNameLookupModal,
    TeamNameSelect,
)
from menus.manageteams.services import delete_team
from utils.player_records import load_player_records, load_teams
from utils.team_manager import team_manager


class TeamPickerView(OwnerBoundView):
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

    # Keep these on the same row, but not row 0 (row 0 may be occupied by the Select width=5)
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


class TeamDeleteConfirmView(OwnerBoundView):
    def __init__(self, *, owner_id: int, team_name: str) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_name = team_name

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Delete Team",
            description=(
                f"Are you sure you want to delete **{self.team_name}**?\n"
                "All members will be removed from the team."
            ),
            color=discord.Color.red(),
        )

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, row=0)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            actual_name, removed_count, removed_ids = await delete_team(interaction, self.team_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
                if team_role:
                    await team_role.delete(reason=f"PPE Team {actual_name} deleted")

                for member_id in removed_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and team_role and team_role in member.roles:
                        await member.remove_roles(team_role)
            except discord.Forbidden:
                role_notice = "\n⚠️ Team deleted, but I could not clean up one or more role assignments."
            except Exception:
                role_notice = "\n⚠️ Team deleted, but role cleanup was partial."

        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)
        await interaction.followup.send(
            f"✅ Deleted **{actual_name}** and removed **{removed_count}** member assignments.{role_notice}",
            ephemeral=True,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_team_manage_view

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)


class ManageSingleTeamView(OwnerBoundView):
    """View for managing a single team with all member actions."""

    def __init__(
        self,
        *,
        owner_id: int,
        team_name: str,
        team: TeamData,
        member_rows: list[tuple[int, str, float, float, float, str]],
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_name = team_name
        self.team = team
        self.member_rows = member_rows

    def current_embed(self) -> discord.Embed:
        total_points = sum(member[4] for member in self.member_rows)
        leader_label = f"<@{self.team.leader_id}>" if self.team.leader_id else "Unassigned"

        embed = discord.Embed(
            title=f"Manage Team - {self.team_name}",
            description=(
                f"Leader: {leader_label}\n"
                f"Members: **{len(self.member_rows)}**\n"
                f"Team Total Contribution: **{total_points:.1f}** pts"
            ),
            color=discord.Color.blurple(),
        )

        if not self.member_rows:
            embed.add_field(name="Members", value="No members yet.", inline=False)
            return embed

        lines: list[str] = []
        for rank, (_member_id, member_name, ppe_points, quest_points, contribution, best_class) in enumerate(self.member_rows, start=1):
            lines.append(
                f"{rank}. **{member_name}** ({best_class}): {ppe_points:.1f} PPE + {quest_points:.1f} Quest = **{contribution:.1f}**"
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

        if not self.member_rows:
            embed = discord.Embed(
                title=f"Team Info - {self.team_name}",
                description=f"Leader: {leader_label}",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Members", value="0", inline=True)
            embed.add_field(name="Total: PPE + Quest", value=f"{total_ppe:.1f} + {total_quest:.1f} = **{total_points:.1f}**", inline=True)
            embed.add_field(name="Rankings", value="This team has no members yet.", inline=False)
            return [embed]

        lines = [
            (
                f"{rank}. {member_name}: {ppe_points:.1f} PPE + {quest_points:.1f} "
                f"Quest = **{contribution:.1f}** pts ({best_class})"
            )
            for rank, (_member_id, member_name, ppe_points, quest_points, contribution, best_class) in enumerate(
                self.member_rows,
                start=1,
            )
        ]

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
            embed.add_field(
                name="Total: PPE + Quest",
                value=f"{total_ppe:.1f} + {total_quest:.1f} = **{total_points:.1f}**",
                inline=True,
            )

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
        view = TeamDeleteConfirmView(owner_id=self.owner_id, team_name=self.team_name)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        from menus.manageteams.entry import open_manage_teams_home

        await open_manage_teams_home(interaction, owner_id=self.owner_id)


class TeamInfoPreviewView(OwnerBoundView):
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


class ManageTeamsHomeView(OwnerBoundView):
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
        teams = await load_teams(interaction)
        ordered_names = sorted(teams.keys(), key=lambda name: name.lower())
        picker = TeamPickerView(owner_id=self.owner_id, team_names=ordered_names)
        await interaction.response.edit_message(embed=picker.current_embed(), view=picker)

    @discord.ui.button(label="Team Leaderboard", style=discord.ButtonStyle.primary, row=1)
    async def team_leaderboard(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        data = await team_manager.get_team_leaderboard_data(interaction)
        if not data:
            await interaction.response.send_message("No teams available yet.", ephemeral=True)
            return

        rows = [
            f"**{team_name}** - {ppe_points:.1f} PPE + {quest_points} Quest = **{total_points:.1f}** pts ({member_count} members)"
            for team_name, _leader_id, ppe_points, quest_points, total_points, member_count in data
        ]
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


class LeaderboardPreviewView(OwnerBoundView):
    def __init__(self, *, owner_id: int, embeds: list[discord.Embed]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.embeds = embeds
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
