"""Team membership workflows that combine data updates with Discord role assignment."""

from __future__ import annotations

import discord

from dataclass import TeamData
from utils.team_manager import team_manager


async def assign_team_role(
    guild: discord.Guild | None,
    member_or_id: discord.Member | int,
    team_name: str,
) -> bool:
    """Give a member the Discord role named after their team, if both exist.

    Returns False only when the bot lacks permission to assign the role; a missing
    member/role is treated as "nothing to do" and returns True.
    """
    if guild is None:
        return True

    if isinstance(member_or_id, discord.Member):
        member: discord.Member | None = member_or_id
    else:
        member = guild.get_member(member_or_id)
        if member is None:
            try:
                member = await guild.fetch_member(member_or_id)
            except Exception:
                member = None

    if member is None:
        return True

    role = discord.utils.get(guild.roles, name=team_name)
    if role is None or role in member.roles:
        return True

    try:
        await member.add_roles(role)
    except discord.Forbidden:
        return False
    return True


async def add_player_to_team_with_role(
    interaction: discord.Interaction,
    player_or_member: discord.Member | int,
    team_name: str,
) -> tuple[TeamData, bool]:
    """Add a PPE player to a team and assign the team role.

    Raises ``ValueError`` for validation failures (unknown team, not a PPE player, already on a team).
    Returns ``(team, role_assigned_ok)``.
    """
    player_id = player_or_member.id if isinstance(player_or_member, discord.Member) else int(player_or_member)
    team = await team_manager.add_player_to_team(interaction, player_id, team_name)
    role_ok = await assign_team_role(interaction.guild, player_or_member, team.name)
    return team, role_ok


__all__ = ["add_player_to_team_with_role", "assign_team_role"]
