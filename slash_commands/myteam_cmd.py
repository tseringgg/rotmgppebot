from __future__ import annotations

from typing import Optional

import discord

from utils.player_records import ensure_player_exists, load_player_records, load_teams
from utils.team_manager import team_manager


def _format_class_name(raw_class: object) -> str:
    return str(getattr(raw_class, "value", raw_class))


def _team_state_embed(title: str, description: str, *, color: discord.Color | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.orange(),
    )


async def build_team_embed(
    interaction: discord.Interaction,
    *,
    user_id: int,
    team_name: str | None = None,
    title: str = "My Team",
    no_team_message: str = "Uh oh, you haven't been added to a team yet.",
) -> discord.Embed:
    if not interaction.guild:
        return _team_state_embed(title, "❌ This command can only be used in a server.", color=discord.Color.red())

    teams = await load_teams(interaction)
    if not teams:
        return _team_state_embed(title, "❌ No teams currently exist.")

    target_team = team_name
    if not target_team:
        records = await load_player_records(interaction)
        user_key = ensure_player_exists(records, user_id)
        user_team = records[user_key].team_name if user_key in records else None
        if not user_team:
            return _team_state_embed(title, no_team_message)
        target_team = user_team

    team_info = await team_manager.get_team_members_info(interaction, target_team)
    if not team_info:
        return _team_state_embed(title, f"❌ Team `{target_team}` not found.", color=discord.Color.red())

    team_name_result, leader_id, members_info = team_info
    members_info_sorted = sorted(members_info, key=lambda x: x[2], reverse=True)
    total_points = sum(points for _member_id, _member_name, points, _ppe_class in members_info_sorted)

    leader_text = f"<@{leader_id}>"
    embed = discord.Embed(
        title=f"Team: {team_name_result}",
        description=f"Leader: {leader_text}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Members", value=str(len(members_info_sorted)), inline=True)
    embed.add_field(name="Total Team Points", value=f"{total_points:.1f}", inline=True)

    if members_info_sorted:
        lines: list[str] = []
        for rank, (_member_id, member_name, points, ppe_class) in enumerate(members_info_sorted, start=1):
            lines.append(f"{rank}. {member_name}: {points:.1f} pts ({_format_class_name(ppe_class)})")

        members_text = "\n".join(lines)
        if len(members_text) > 1024:
            members_text = members_text[:1000].rstrip() + "\n..."
        embed.add_field(name="Rankings", value=members_text, inline=False)
    else:
        embed.add_field(
            name="Rankings",
            value="This team has no active members with PPE characters.",
            inline=False,
        )

    return embed


async def command(interaction: discord.Interaction, team_name: Optional[str] = None):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        embed = await build_team_embed(
            interaction,
            user_id=interaction.user.id,
            team_name=team_name,
            title="My Team",
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
