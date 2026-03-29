from __future__ import annotations

import discord

from dataclass import TeamData
from menus.manageteams.common import TEAM_LIST_PAGE_SIZE, display_name, resolve_team_name
from utils.player_records import ensure_player_exists, load_player_records, load_teams
from utils.team_manager import team_manager
from utils.team_contest_scoring import compute_team_member_points, load_team_contest_scoring


async def create_empty_team(interaction: discord.Interaction, team_name: str) -> TeamData:
    async def operation(teams, records, _interaction):
        for existing_name in teams:
            if existing_name.lower() == team_name.lower():
                raise ValueError(f"❌ Team `{existing_name}` already exists.")
        team = TeamData(name=team_name, leader_id=0, members=[])
        teams[team_name] = team
        return team

    return await team_manager.execute_transaction(interaction, operation)


async def delete_team(interaction: discord.Interaction, team_name: str) -> tuple[str, int, list[int]]:
    async def operation(teams, records, _interaction):
        actual_name = resolve_team_name(teams, team_name)
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


async def remove_members_from_team(
    interaction: discord.Interaction,
    *,
    team_name: str,
    member_ids: list[int],
) -> tuple[str, int, list[int], int]:
    async def operation(teams, records, _interaction):
        actual_name = resolve_team_name(teams, team_name)
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


async def set_team_leader(interaction: discord.Interaction, *, team_name: str, leader_id: int) -> tuple[str, int]:
    async def operation(teams, records, _interaction):
        actual_name = resolve_team_name(teams, team_name)
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


async def build_team_summary_pages(interaction: discord.Interaction) -> list[discord.Embed]:
    teams = await load_teams(interaction)
    records = await load_player_records(interaction)
    scoring = await load_team_contest_scoring(interaction)

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
        quest_points = 0.0
        for member_id in team.members:
            player_data = records.get(member_id)
            if not player_data:
                continue

            member_ppe_points, member_quest_points, _member_total = compute_team_member_points(
                player_data,
                scoring=scoring,
            )
            ppe_points += member_ppe_points
            quest_points += member_quest_points

        total_points = ppe_points + quest_points
        leader_name = display_name(interaction.guild, team.leader_id) if team.leader_id else "Unassigned"
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
            f"Team quest scoring: **{'Enabled' if scoring.include_quest_points else 'Disabled'}**",
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


async def build_team_detail(
    interaction: discord.Interaction,
    *,
    team_name: str,
) -> tuple[str, TeamData, list[tuple[int, str, float, float, float, str]], bool]:
    teams = await load_teams(interaction)
    records = await load_player_records(interaction)
    scoring = await load_team_contest_scoring(interaction)

    actual_name = resolve_team_name(teams, team_name)
    if not actual_name:
        raise ValueError(f"❌ Team `{team_name}` not found.")

    team = teams[actual_name]
    members: list[tuple[int, str, float, float, float, str]] = []
    for member_id in team.members:
        player = records.get(member_id)
        member_name = display_name(interaction.guild, member_id)
        ppe_points = 0.0
        best_class = "No PPE"

        if player and player.ppes:
            best_ppe = max(player.ppes, key=lambda p: p.points)
            ppe_points = best_ppe.points
            best_class = str(best_ppe.name)

        _best_ppe_points, quest_points, contribution = compute_team_member_points(
            player,
            scoring=scoring,
        )
        members.append((member_id, member_name, ppe_points, quest_points, contribution, best_class))

    members.sort(key=lambda entry: entry[4], reverse=True)
    return actual_name, team, members, scoring.include_quest_points
