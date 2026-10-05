from __future__ import annotations

from typing import Optional

import discord

from menus.menu_utils import OwnerBoundView
from menus.menu_utils.embed_pager_view import OwnerBoundEmbedPagerView
from menus.menu_utils.team_loot_image import add_team_loot_image_buttons
from utils.guild_config import load_guild_config
from utils.player_records import ensure_player_exists, load_player_records, load_teams, resolve_team_name
from utils.team_contest_scoring import (
    TeamContestScoring,
    compute_team_member_points,
    format_points_breakdown,
    get_best_ppe,
    load_team_contest_scoring,
    total_points_label,
)
from utils.team_manager import team_manager


def _format_class_name(raw_class: object) -> str:
    if raw_class is None:
        return "No Character"
    return str(getattr(raw_class, "value", raw_class))


def _team_state_embed(title: str, description: str, *, color: discord.Color | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.orange(),
    )


def _split_lines(lines: list[str], *, page_size: int) -> list[list[str]]:
    if not lines:
        return [[]]

    pages: list[list[str]] = []
    for index in range(0, len(lines), page_size):
        pages.append(lines[index:index + page_size])
    return pages


def _build_members_with_scoring(
    *,
    records: dict,
    members_info: list[tuple[int, str, float, str]],
    include_quest_points: bool,
    scoring: TeamContestScoring,
    guild_config: dict | None = None,
) -> list[tuple[int, str, float, float, float, str]]:
    members_with_scoring: list[tuple[int, str, float, float, float, str]] = []
    for member_id, member_name, _legacy_ppe_points, _legacy_ppe_class in members_info:
        player_data = records.get(member_id)
        computed_ppe_points, computed_quest_points, _computed_total = compute_team_member_points(
            player_data,
            scoring=scoring,
            aggregate=scoring.team_aggregate_points,
            guild_config=guild_config,
        )

        if player_data and getattr(player_data, "ppes", None):
            if scoring.team_aggregate_points:
                ppe_class = "All PPEs"
            else:
                best_ppe = get_best_ppe(player_data, guild_config=guild_config)
                ppe_class = _format_class_name(getattr(best_ppe, "name", None))
        else:
            ppe_class = "No Character"

        quest_points = computed_quest_points if include_quest_points else 0.0
        contribution = computed_ppe_points + quest_points
        members_with_scoring.append(
            (
                member_id,
                member_name,
                computed_ppe_points,
                quest_points,
                contribution,
                ppe_class,
            )
        )

    members_with_scoring.sort(key=lambda entry: entry[4], reverse=True)
    return members_with_scoring


def _build_ranking_line(
    *,
    rank: int,
    member_name: str,
    ppe_points: float,
    quest_points: float,
    contribution: float,
    ppe_class: str,
    include_quest_points: bool,
) -> str:
    breakdown = format_points_breakdown(
        ppe_points=ppe_points,
        quest_points=quest_points,
        total_points=contribution,
        include_quest_points=include_quest_points,
    )
    return f"{rank}. {member_name}: {breakdown} pts ({ppe_class})"


DEFAULT_NO_TEAM_MESSAGE = "Uh oh, you haven't been added to a team yet."


async def resolve_team_target(
    interaction: discord.Interaction,
    *,
    user_id: int,
    team_name: str | None = None,
    title: str = "My Team",
    no_team_message: str = DEFAULT_NO_TEAM_MESSAGE,
) -> tuple[str | None, discord.Embed | None]:
    """Resolve which team to show: the explicit ``team_name`` or the user's own team.

    Returns ``(canonical_team_name, None)`` on success, or ``(None, state_embed)`` explaining why not.
    """
    if not interaction.guild:
        return None, _team_state_embed(title, "❌ This command can only be used in a server.", color=discord.Color.red())

    teams = await load_teams(interaction)
    if not teams:
        return None, _team_state_embed(title, "❌ No teams currently exist.")

    requested_team = team_name
    if not requested_team:
        records = await load_player_records(interaction)
        user_key = ensure_player_exists(records, user_id)
        requested_team = records[user_key].team_name if user_key in records else None
        if not requested_team:
            return None, _team_state_embed(title, no_team_message)

    actual_team = resolve_team_name(teams, requested_team)
    if actual_team is None:
        return None, _team_state_embed(title, f"❌ Team `{requested_team}` not found.", color=discord.Color.red())
    return actual_team, None


async def build_team_embeds(
    interaction: discord.Interaction,
    *,
    user_id: int,
    team_name: str | None = None,
    title: str = "My Team",
    no_team_message: str = DEFAULT_NO_TEAM_MESSAGE,
    page_size: int = 15,
) -> list[discord.Embed]:
    """Resolve the target team and build its paginated ranking embeds (or a single state embed)."""
    target_team, error_embed = await resolve_team_target(
        interaction,
        user_id=user_id,
        team_name=team_name,
        title=title,
        no_team_message=no_team_message,
    )
    if target_team is None:
        return [error_embed]
    return await build_team_embeds_for(interaction, team_name=target_team, title=title, page_size=page_size)


async def build_team_embeds_for(
    interaction: discord.Interaction,
    *,
    team_name: str,
    title: str = "My Team",
    page_size: int = 15,
) -> list[discord.Embed]:
    """Build paginated ranking embeds for an already-resolved team name."""
    records = await load_player_records(interaction)
    scoring = await load_team_contest_scoring(interaction)
    guild_config = await load_guild_config(interaction)

    team_info = await team_manager.get_team_members_info(interaction, team_name)
    if not team_info:
        return [_team_state_embed(title, f"❌ Team `{team_name}` not found.", color=discord.Color.red())]

    team_name_result, leader_id, members_info = team_info
    members_info_sorted = _build_members_with_scoring(
        records=records,
        members_info=members_info,
        include_quest_points=scoring.include_quest_points,
        scoring=scoring,
        guild_config=guild_config,
    )

    total_ppe = sum(x[2] for x in members_info_sorted)
    total_quest = sum(x[3] for x in members_info_sorted)
    total_points = total_ppe + total_quest
    total_label = total_points_label(include_quest_points=scoring.include_quest_points)
    total_breakdown = format_points_breakdown(
        ppe_points=total_ppe,
        quest_points=total_quest,
        total_points=total_points,
        include_quest_points=scoring.include_quest_points,
    )

    embed_title = f"{title} - {team_name_result}" if title and title != "My Team" else f"Team Info - {team_name_result}"

    if not members_info_sorted:
        embed = discord.Embed(
            title=embed_title,
            description=f"Leader: <@{leader_id}>",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Members", value="0", inline=True)
        embed.add_field(name=total_label, value=total_breakdown, inline=True)
        embed.add_field(
            name="Rankings",
            value="This team has no active members with PPE characters.",
            inline=False,
        )
        return [embed]

    all_lines: list[str] = []
    for rank, (_member_id, member_name, ppe_points, quest_points, contribution, ppe_class) in enumerate(
        members_info_sorted,
        start=1,
    ):
        all_lines.append(
            _build_ranking_line(
                rank=rank,
                member_name=member_name,
                ppe_points=ppe_points,
                quest_points=quest_points,
                contribution=contribution,
                ppe_class=ppe_class,
                include_quest_points=scoring.include_quest_points,
            )
        )

    line_pages = _split_lines(all_lines, page_size=page_size)
    embeds: list[discord.Embed] = []
    page_total = len(line_pages)
    for page_number, page_lines in enumerate(line_pages, start=1):
        embed = discord.Embed(
            title=embed_title,
            description=f"Leader: <@{leader_id}>",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Members", value=str(len(members_info_sorted)), inline=True)
        embed.add_field(name=total_label, value=total_breakdown, inline=True)
        embed.add_field(name="Rankings", value="\n".join(page_lines), inline=False)
        if page_total > 1:
            embed.set_footer(text=f"Page {page_number}/{page_total}")
        embeds.append(embed)

    return embeds


def _scoring_mode_label(scoring: TeamContestScoring) -> str:
    base = "Aggregate PPE" if scoring.team_aggregate_points else "Best PPE"
    if scoring.include_quest_points:
        return f"{base} + Quest"
    return base


def build_team_overview_embed(
    *,
    team_name: str,
    leader_id: int | None,
    members_info_sorted: list[tuple[int, str, float, float, float, str]],
    scoring: TeamContestScoring,
) -> discord.Embed:
    leader_label = f"<@{leader_id}>" if leader_id else "Unassigned"
    scoring_mode = _scoring_mode_label(scoring)
    total_ppe = sum(x[2] for x in members_info_sorted)
    total_quest = sum(x[3] for x in members_info_sorted)
    total_points = total_ppe + total_quest

    embed = discord.Embed(
        title=f"Team Overview - {team_name}",
        description=(
            f"Leader: {leader_label}\n"
            f"Members: **{len(members_info_sorted)}**\n"
            f"Scoring Mode: **{scoring_mode}**\n"
            f"Team Total Contribution: **{total_points:.1f}** pts"
        ),
        color=discord.Color.blurple(),
    )

    if not members_info_sorted:
        embed.add_field(name="Members", value="This team has no active members with PPE characters.", inline=False)
        return embed

    lines: list[str] = []
    for rank, (_member_id, member_name, ppe_points, quest_points, contribution, ppe_class) in enumerate(
        members_info_sorted,
        start=1,
    ):
        breakdown = format_points_breakdown(
            ppe_points=ppe_points,
            quest_points=quest_points,
            total_points=contribution,
            include_quest_points=scoring.include_quest_points,
        )
        lines.append(f"{rank}. **{member_name}** ({ppe_class}): {breakdown}")

    text = "\n".join(lines)
    if len(text) > 1024:
        text = text[:1000].rstrip() + "\n..."
    embed.add_field(name="Member Contributions", value=text, inline=False)
    return embed


class MyTeamOverviewView(OwnerBoundView):
    """Team overview view with button to open detailed Team Info."""

    def __init__(
        self,
        *,
        owner_id: int,
        team_name: str,
        overview_embed: discord.Embed,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.team_name = team_name
        self.overview_embed = overview_embed

    @discord.ui.button(label="Team Info", style=discord.ButtonStyle.primary, row=0)
    async def team_info(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embeds = await build_team_embeds_for(interaction, team_name=self.team_name)
        view = MyTeamInfoView(
            owner_id=self.owner_id,
            embeds=embeds,
            team_name=self.team_name,
            overview_embed=self.overview_embed,
        )
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class MyTeamInfoView(OwnerBoundEmbedPagerView):
    """Paginated /myteam view with team rankings, back button, and team loot image buttons."""

    def __init__(
        self,
        *,
        owner_id: int,
        embeds: list[discord.Embed],
        team_name: str,
        overview_embed: discord.Embed,
    ) -> None:
        super().__init__(owner_id=owner_id, embeds=embeds, timeout=600)
        self.team_name = team_name
        self.overview_embed = overview_embed
        add_team_loot_image_buttons(self, team_name=team_name, row=2, command_name="/myteam")

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = MyTeamOverviewView(
            owner_id=self.owner_id,
            team_name=self.team_name,
            overview_embed=self.overview_embed,
        )
        await interaction.response.edit_message(embed=self.overview_embed, view=view)


# Alias for backward compatibility
MyTeamView = MyTeamOverviewView


async def command(interaction: discord.Interaction, team_name: Optional[str] = None):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        target_team, error_embed = await resolve_team_target(
            interaction,
            user_id=interaction.user.id,
            team_name=team_name,
        )
        if target_team is None:
            return await interaction.response.send_message(embed=error_embed)

        team_info = await team_manager.get_team_members_info(interaction, target_team)
        if not team_info:
            return await interaction.response.send_message(
                embed=_team_state_embed("My Team", f"❌ Team `{target_team}` not found.", color=discord.Color.red())
            )

        team_name_result, leader_id, members_info = team_info
        records = await load_player_records(interaction)
        scoring = await load_team_contest_scoring(interaction)
        guild_config = await load_guild_config(interaction)

        members_info_sorted = _build_members_with_scoring(
            records=records,
            members_info=members_info,
            include_quest_points=scoring.include_quest_points,
            scoring=scoring,
            guild_config=guild_config,
        )

        overview_embed = build_team_overview_embed(
            team_name=team_name_result,
            leader_id=leader_id,
            members_info_sorted=members_info_sorted,
            scoring=scoring,
        )
        view = MyTeamOverviewView(
            owner_id=interaction.user.id,
            team_name=team_name_result,
            overview_embed=overview_embed,
        )
        await interaction.response.send_message(embed=overview_embed, view=view)
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
