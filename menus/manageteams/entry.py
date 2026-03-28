from __future__ import annotations

import re

import discord

from dataclass import TeamData
from menus.leaderboard.common import (
    LEADERBOARD_PAGE_SIZE,
    build_leaderboard_embeds,
    build_ranked_entry_lines,
)
from menus.menu_utils import OwnerBoundView
from utils.guild_config import get_quest_points
from utils.player_records import (
    ensure_player_exists,
    load_player_records,
    load_teams,
)
from utils.team_manager import team_manager

TEAM_LIST_PAGE_SIZE = 12


def _resolve_team_name(teams: dict[str, TeamData], requested_name: str) -> str | None:
    for team_name in teams:
        if team_name.lower() == requested_name.lower():
            return team_name
    return None


def _display_name(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(user_id)
    if member is None:
        return f"Unknown User ({user_id})"
    return member.display_name


def _parse_id_token(raw_value: str) -> int | None:
    token = str(raw_value).strip()
    if not token:
        return None

    mention_match = re.fullmatch(r"<@!?(\d+)>", token)
    if mention_match:
        return int(mention_match.group(1))

    if token.isdigit():
        return int(token)
    return None


def _resolve_single_name_query(candidates: list[tuple[int, str]], query: str, *, context_label: str) -> tuple[int | None, str | None]:
    token = str(query).strip()
    if not token:
        return None, f"❌ Please provide a {context_label} name, mention, or user ID."

    parsed_id = _parse_id_token(token)
    if parsed_id is not None:
        for candidate_id, _candidate_name in candidates:
            if candidate_id == parsed_id:
                return candidate_id, None
        return None, f"❌ No {context_label} matched that user ID."

    lowered = token.lower()
    exact_matches = [entry for entry in candidates if entry[1].lower() == lowered]
    if len(exact_matches) == 1:
        return exact_matches[0][0], None
    if len(exact_matches) > 1:
        names = ", ".join(name for _id, name in exact_matches[:5])
        return None, f"❌ Multiple exact matches found: {names}. Please use a mention or user ID."

    startswith_matches = [entry for entry in candidates if entry[1].lower().startswith(lowered)]
    if len(startswith_matches) == 1:
        return startswith_matches[0][0], None

    contains_matches = [entry for entry in candidates if lowered in entry[1].lower()]
    if len(contains_matches) == 1:
        return contains_matches[0][0], None

    matches = startswith_matches or contains_matches
    if matches:
        preview = ", ".join(name for _id, name in matches[:8])
        return None, f"❌ Multiple matches found. Be more specific: {preview}"

    return None, f"❌ No {context_label} matched '{token}'."


def _resolve_team_name_query(team_names: list[str], query: str) -> tuple[str | None, str | None]:
    token = str(query).strip()
    if not token:
        return None, "❌ Team name cannot be empty."

    lowered = token.lower()
    exact = [name for name in team_names if name.lower() == lowered]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "❌ Multiple teams have the same exact name. Please use a more specific query."

    startswith = [name for name in team_names if name.lower().startswith(lowered)]
    if len(startswith) == 1:
        return startswith[0], None

    contains = [name for name in team_names if lowered in name.lower()]
    if len(contains) == 1:
        return contains[0], None

    matches = startswith or contains
    if matches:
        return None, f"❌ Multiple team matches found: {', '.join(matches[:8])}. Please refine your input."

    return None, f"❌ No team matched '{token}'."


async def _create_empty_team(interaction: discord.Interaction, team_name: str) -> TeamData:
    async def operation(teams, records, _interaction):
        for existing_name in teams:
            if existing_name.lower() == team_name.lower():
                raise ValueError(f"❌ Team `{existing_name}` already exists.")
        team = TeamData(name=team_name, leader_id=0, members=[])
        teams[team_name] = team
        return team

    return await team_manager.execute_transaction(interaction, operation)


async def _delete_team(interaction: discord.Interaction, team_name: str) -> tuple[str, int, list[int]]:
    async def operation(teams, records, _interaction):
        actual_name = _resolve_team_name(teams, team_name)
        if not actual_name:
            raise ValueError(f"❌ Team `{team_name}` not found.")

        deleted_team = teams.pop(actual_name)
        removed_member_ids: list[int] = []
        for member_id in deleted_team.members:
            key = ensure_player_exists(records, member_id)
            if records[key].team_name and records[key].team_name.lower() == actual_name.lower():
                records[key].team_name = None
                removed_member_ids.append(member_id)

        return actual_name, len(removed_member_ids), removed_member_ids

    return await team_manager.execute_transaction(interaction, operation)


async def _remove_members_from_team(
    interaction: discord.Interaction,
    *,
    team_name: str,
    member_ids: list[int],
) -> tuple[str, int, list[int], int]:
    async def operation(teams, records, _interaction):
        actual_name = _resolve_team_name(teams, team_name)
        if not actual_name:
            raise ValueError(f"❌ Team `{team_name}` not found.")

        team = teams[actual_name]
        removed_ids: list[int] = []
        for member_id in member_ids:
            if member_id in team.members:
                team.members.remove(member_id)
                key = ensure_player_exists(records, member_id)
                if records[key].team_name and records[key].team_name.lower() == actual_name.lower():
                    records[key].team_name = None
                removed_ids.append(member_id)

        if team.leader_id in removed_ids:
            team.leader_id = team.members[0] if team.members else 0

        return actual_name, len(removed_ids), removed_ids, team.leader_id

    return await team_manager.execute_transaction(interaction, operation)


async def _set_team_leader(interaction: discord.Interaction, *, team_name: str, leader_id: int) -> tuple[str, int]:
    async def operation(teams, records, _interaction):
        actual_name = _resolve_team_name(teams, team_name)
        if not actual_name:
            raise ValueError(f"❌ Team `{team_name}` not found.")

        team = teams[actual_name]
        if leader_id not in team.members:
            team.members.append(leader_id)

        key = ensure_player_exists(records, leader_id)
        if not records[key].is_member:
            raise ValueError("❌ Team leader must be a PPE contest member.")

        records[key].team_name = actual_name
        team.leader_id = leader_id
        return actual_name, team.leader_id

    return await team_manager.execute_transaction(interaction, operation)


async def _build_team_summary_pages(interaction: discord.Interaction) -> list[discord.Embed]:
    teams = await load_teams(interaction)
    records = await load_player_records(interaction)
    regular_qp, shiny_qp, skin_qp = await get_quest_points(interaction)

    if not teams:
        return [
            discord.Embed(
                title="Manage Teams",
                description=(
                    "No teams exist yet.\n\n"
                    "Use **Create New Team** to start with an empty team, then assign members and a leader."
                ),
                color=discord.Color.orange(),
            )
        ]

    team_rows: list[tuple[str, str]] = []
    all_members: set[int] = set()
    teams_with_leader = 0

    for team_name, team in sorted(teams.items(), key=lambda item: item[0].lower()):
        all_members.update(team.members)
        if team.leader_id:
            teams_with_leader += 1

        ppe_points = 0.0
        quest_points = 0
        for member_id in team.members:
            player_data = records.get(member_id)
            if not player_data:
                continue

            if player_data.ppes:
                best_points = max(ppe.points for ppe in player_data.ppes)
                ppe_points += best_points

            quest_points += (
                len(player_data.quests.completed_items) * regular_qp
                + len(player_data.quests.completed_shinies) * shiny_qp
                + len(player_data.quests.completed_skins) * skin_qp
            )

        total_points = ppe_points + quest_points
        leader_name = _display_name(interaction.guild, team.leader_id) if team.leader_id else "Unassigned"
        row = (
            f"**{team_name}**",
            f"Leader: {leader_name} | Members: {len(team.members)} | Total: {total_points:.1f} pts",
        )
        team_rows.append(row)

    pages: list[list[tuple[str, str]]] = []
    for index in range(0, len(team_rows), TEAM_LIST_PAGE_SIZE):
        pages.append(team_rows[index:index + TEAM_LIST_PAGE_SIZE])

    embeds: list[discord.Embed] = []
    for page_index, page_rows in enumerate(pages, start=1):
        summary_lines = [
            f"Teams: **{len(teams)}**",
            f"Players in teams: **{len(all_members)}**",
            f"Teams with leader assigned: **{teams_with_leader}**",
            "",
            "Use **Manage Team** to edit a team, or **Create New Team** to add one.",
        ]

        list_lines = [f"{title}\n{details}" for title, details in page_rows]

        embed = discord.Embed(
            title="Manage Teams",
            description="\n".join(summary_lines),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Teams", value="\n\n".join(list_lines), inline=False)
        if len(pages) > 1:
            embed.set_footer(text=f"Team List Page {page_index}/{len(pages)}")
        embeds.append(embed)

    return embeds


async def _build_team_detail(
    interaction: discord.Interaction,
    *,
    team_name: str,
) -> tuple[str, TeamData, list[tuple[int, str, float, float, float, str]]]:
    teams = await load_teams(interaction)
    records = await load_player_records(interaction)
    regular_qp, shiny_qp, skin_qp = await get_quest_points(interaction)

    actual_name = _resolve_team_name(teams, team_name)
    if not actual_name:
        raise ValueError(f"❌ Team `{team_name}` not found.")

    team = teams[actual_name]
    members: list[tuple[int, str, float, float, float, str]] = []
    for member_id in team.members:
        player = records.get(member_id)
        member_name = _display_name(interaction.guild, member_id)
        best_points = 0.0
        best_class = "No PPE"

        if player and player.ppes:
            best_ppe = max(player.ppes, key=lambda p: p.points)
            best_points = best_ppe.points
            best_class = str(best_ppe.name)

        quest_points = 0.0
        if player:
            quest_points = float(
                len(player.quests.completed_items) * regular_qp
                + len(player.quests.completed_shinies) * shiny_qp
                + len(player.quests.completed_skins) * skin_qp
            )

        contribution = best_points + quest_points
        members.append((member_id, member_name, best_points, quest_points, contribution, best_class))

    members.sort(key=lambda entry: entry[4], reverse=True)
    return actual_name, team, members


class CreateTeamModal(discord.ui.Modal, title="Create New Team"):
    team_name = discord.ui.TextInput(label="Team Name", max_length=64, placeholder="Enter team name")

    def __init__(self, *, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        new_name = str(self.team_name.value).strip()
        if not new_name:
            await interaction.response.send_message("❌ Team name cannot be empty.", ephemeral=True)
            return

        try:
            team = await _create_empty_team(interaction, new_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                existing_role = discord.utils.get(interaction.guild.roles, name=team.name)
                if not existing_role:
                    await interaction.guild.create_role(name=team.name, reason=f"PPE Team role for {team.name}")
            except discord.Forbidden:
                role_notice = "\n⚠️ Team created, but I cannot create roles in this server."
            except Exception:
                role_notice = "\n⚠️ Team created, but role creation failed."

        pages = await _build_team_summary_pages(interaction)
        home_view = ManageTeamsHomeView(owner_id=self.owner_id, pages=pages)
        await interaction.response.edit_message(embed=home_view.current_embed(), view=home_view)
        await interaction.followup.send(f"✅ Created team **{team.name}**.{role_notice}", ephemeral=True)


class TeamNameSelect(discord.ui.Select):
    def __init__(self, *, team_names: list[str]) -> None:
        options = [discord.SelectOption(label=name, value=name) for name in team_names[:25]]
        super().__init__(
            placeholder="Select a team to manage...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, TeamPickerView):
            await interaction.response.send_message("Invalid menu state.", ephemeral=True)
            return

        await open_team_manage_view(interaction, owner_id=view.owner_id, team_name=self.values[0])


class TeamNameLookupModal(discord.ui.Modal, title="Find Team"):
    team_name = discord.ui.TextInput(
        label="Team Name",
        placeholder="Type full or partial team name",
        max_length=64,
    )

    def __init__(self, *, owner_id: int, team_names: list[str]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_names = list(team_names)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        matched_name, error = _resolve_team_name_query(self.team_names, str(self.team_name.value))
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert matched_name is not None
        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=matched_name)


class RemoveMembersModal(discord.ui.Modal, title="Remove Team Members"):
    members = discord.ui.TextInput(
        label="Members to Remove",
        placeholder="Enter names/mentions/IDs separated by commas",
        style=discord.TextStyle.paragraph,
        max_length=400,
    )

    def __init__(self, *, owner_id: int, team_name: str, member_rows: list[tuple[int, str, float, float, float, str]]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.member_rows = member_rows

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        tokens = [part.strip() for part in str(self.members.value).split(",") if part.strip()]
        if not tokens:
            await interaction.response.send_message("❌ Please provide at least one member to remove.", ephemeral=True)
            return

        candidates = [(member_id, name) for member_id, name, _b, _q, _t, _c in self.member_rows]
        member_ids: list[int] = []
        errors: list[str] = []
        for token in tokens:
            member_id, error = _resolve_single_name_query(candidates, token, context_label="team member")
            if error:
                errors.append(error)
                continue
            assert member_id is not None
            if member_id not in member_ids:
                member_ids.append(member_id)

        if errors:
            await interaction.response.send_message("\n".join(errors[:5]), ephemeral=True)
            return

        try:
            actual_name, removed_count, removed_ids, new_leader_id = await _remove_members_from_team(
                interaction,
                team_name=self.team_name,
                member_ids=member_ids,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild and removed_ids:
            team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
            if team_role:
                for member_id in removed_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and team_role in member.roles:
                        try:
                            await member.remove_roles(team_role)
                        except discord.Forbidden:
                            role_notice = "\n⚠️ Member removal succeeded, but role cleanup failed for one or more users."
                            break

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=actual_name)
        leader_text = f" New leader: <@{new_leader_id}>." if new_leader_id else " Leader is now unassigned."
        await interaction.followup.send(
            f"✅ Removed **{removed_count}** member(s) from **{actual_name}**.{leader_text}{role_notice}",
            ephemeral=True,
        )


class SetLeaderModal(discord.ui.Modal, title="Set Team Leader"):
    leader = discord.ui.TextInput(
        label="New Team Leader",
        placeholder="Enter member name, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, team_name: str, member_rows: list[tuple[int, str, float, float, float, str]]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.member_rows = member_rows

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        candidates = [(member_id, name) for member_id, name, _b, _q, _t, _c in self.member_rows]
        leader_id, error = _resolve_single_name_query(candidates, str(self.leader.value), context_label="team member")
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert leader_id is not None
        try:
            actual_name, _updated_leader_id = await _set_team_leader(
                interaction,
                team_name=self.team_name,
                leader_id=leader_id,
            )
            if interaction.guild:
                leader_member = interaction.guild.get_member(leader_id)
                team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
                if leader_member and team_role and team_role not in leader_member.roles:
                    await leader_member.add_roles(team_role)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Leader updated, but role assignment failed.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
        await interaction.followup.send(f"✅ Updated leader for **{self.team_name}**.", ephemeral=True)


class AddMemberModal(discord.ui.Modal, title="Add Team Member"):
    member = discord.ui.TextInput(
        label="Member to Add",
        placeholder="Enter member name, mention, or ID",
        max_length=100,
    )

    def __init__(self, *, owner_id: int, team_name: str, eligible_members: list[discord.Member]) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name
        self.eligible_members = list(eligible_members)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        candidates = [(member.id, member.display_name) for member in self.eligible_members]
        member_id, error = _resolve_single_name_query(candidates, str(self.member.value), context_label="eligible player")
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        assert member_id is not None
        try:
            team = await team_manager.add_player_to_team(interaction, member_id, self.team_name)
            if interaction.guild:
                member = interaction.guild.get_member(member_id)
                role = discord.utils.get(interaction.guild.roles, name=team.name)
                if member and role and role not in member.roles:
                    await member.add_roles(role)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Player added, but I could not update role assignments.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)
        await interaction.followup.send(f"✅ Added <@{member_id}> to **{self.team_name}**.", ephemeral=True)


class RenameTeamModal(discord.ui.Modal, title="Rename Team"):
    new_name = discord.ui.TextInput(label="New Team Name", max_length=64, placeholder="Enter new team name")

    def __init__(self, *, owner_id: int, team_name: str) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.team_name = team_name

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu belongs to another user.", ephemeral=True)
            return

        updated_name = str(self.new_name.value).strip()
        if not updated_name:
            await interaction.response.send_message("❌ Team name cannot be empty.", ephemeral=True)
            return

        try:
            await team_manager.update_team_name(interaction, self.team_name, updated_name)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        role_notice = ""
        if interaction.guild:
            try:
                old_role = discord.utils.get(interaction.guild.roles, name=self.team_name)
                if old_role:
                    await old_role.edit(name=updated_name, reason=f"PPE Team rename from {self.team_name} to {updated_name}")
            except discord.Forbidden:
                role_notice = "\n⚠️ Team renamed, but role rename failed due to permissions."
            except discord.HTTPException:
                role_notice = "\n⚠️ Team renamed, but role rename failed."

        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=updated_name)
        await interaction.followup.send(f"✅ Renamed **{self.team_name}** to **{updated_name}**.{role_notice}", ephemeral=True)


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

    @discord.ui.button(label="Find Team", style=discord.ButtonStyle.primary, row=0)
    async def find_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not self.team_names:
            await interaction.response.send_message("❌ No teams exist yet.", ephemeral=True)
            return
        await interaction.response.send_modal(TeamNameLookupModal(owner_id=self.owner_id, team_names=self.team_names))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
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
            actual_name, removed_count, removed_ids = await _delete_team(interaction, self.team_name)
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

        await open_manage_teams_home(interaction, owner_id=self.owner_id)
        await interaction.followup.send(
            f"✅ Deleted **{actual_name}** and removed **{removed_count}** member assignments.{role_notice}",
            ephemeral=True,
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await open_team_manage_view(interaction, owner_id=self.owner_id, team_name=self.team_name)


class ManageSingleTeamView(OwnerBoundView):
    """View for managing a single team with all member actions.
    
    Button Layout:
    - Row 0: Add Member (green), Set Leader (green), Rename Team (green), Team Info (blue)
    - Row 1: Remove Members (red), Delete Team (red), Back (gray)
    """
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
        """Generate the current team information embed."""
        total_points = sum(member[4] for member in self.member_rows)
        if self.team.leader_id:
            leader_label = f"<@{self.team.leader_id}>"
        else:
            leader_label = "Unassigned"

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
        for rank, (member_id, member_name, ppe_points, quest_points, contribution, best_class) in enumerate(self.member_rows, start=1):
            lines.append(
                f"{rank}. **{member_name}** ({best_class}): {ppe_points:.1f} PPE + {quest_points:.1f} Quest = **{contribution:.1f}**"
            )

        text = "\n".join(lines)
        if len(text) > 1024:
            text = text[:1000].rstrip() + "\n..."
        embed.add_field(name="Member Contributions", value=text, inline=False)
        return embed

    # === ROW 0: Add Member, Set Leader, Rename Team, Team Info ===
    @discord.ui.button(label="Add Member", style=discord.ButtonStyle.success, row=0)
    async def add_member(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Add a member to the team using modal-based name resolution."""
        records = await load_player_records(interaction)
        teams = await load_teams(interaction)
        actual_name = _resolve_team_name(teams, self.team_name)
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
        """Set the team leader from current members."""
        if not self.member_rows:
            await interaction.response.send_message("❌ This team has no members. Add one before setting leader.", ephemeral=True)
            return
        await interaction.response.send_modal(
            SetLeaderModal(owner_id=self.owner_id, team_name=self.team_name, member_rows=self.member_rows)
        )

    @discord.ui.button(label="Rename Team", style=discord.ButtonStyle.success, row=0)
    async def rename_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Rename the team."""
        await interaction.response.send_modal(RenameTeamModal(owner_id=self.owner_id, team_name=self.team_name))

    @discord.ui.button(label="Team Info", style=discord.ButtonStyle.primary, row=0)
    async def team_info(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """View detailed team information with PPE and quest point breakdown."""
        from slash_commands.myteam_cmd import build_team_embeds

        embeds = await build_team_embeds(
            interaction,
            user_id=interaction.user.id,
            team_name=self.team_name,
            title=f"Team Info - {self.team_name}",
        )
        view = TeamInfoPreviewView(owner_id=self.owner_id, embeds=embeds, team_name=self.team_name)
        await interaction.response.edit_message(embed=view.embeds[0], view=view)

    # === ROW 1: Remove Members, Delete Team, Back ===
    @discord.ui.button(label="Remove Members", style=discord.ButtonStyle.danger, row=1)
    async def remove_selected(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Remove members from the team using modal-based name resolution."""
        if not self.member_rows:
            await interaction.response.send_message("❌ This team has no members to remove.", ephemeral=True)
            return
        await interaction.response.send_modal(
            RemoveMembersModal(owner_id=self.owner_id, team_name=self.team_name, member_rows=self.member_rows)
        )

    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.danger, row=1)
    async def delete_team(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Delete the entire team - requires confirmation."""
        view = TeamDeleteConfirmView(owner_id=self.owner_id, team_name=self.team_name)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Return to the team picker view."""
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


async def open_manage_teams_home(interaction: discord.Interaction, *, owner_id: int) -> None:
    pages = await _build_team_summary_pages(interaction)
    view = ManageTeamsHomeView(owner_id=owner_id, pages=pages)
    await interaction.response.edit_message(embed=view.current_embed(), view=view)


async def open_team_manage_view(interaction: discord.Interaction, *, owner_id: int, team_name: str) -> None:
    try:
        actual_name, team, member_rows = await _build_team_detail(interaction, team_name=team_name)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    view = ManageSingleTeamView(
        owner_id=owner_id,
        team_name=actual_name,
        team=team,
        member_rows=member_rows,
    )
    await interaction.response.edit_message(embed=view.current_embed(), view=view)


async def open_manage_teams_menu(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    pages = await _build_team_summary_pages(interaction)
    view = ManageTeamsHomeView(owner_id=interaction.user.id, pages=pages)
    await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
