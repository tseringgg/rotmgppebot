"""Command to add a player to the PPE contest (and optionally to a team)."""

import discord

from utils.player_manager import player_manager
from utils.player_records import load_teams, resolve_team_name
from utils.role_checks import ppe_player_role
from utils.team_membership import add_player_to_team_with_role


async def _ensure_ppe_player(interaction: discord.Interaction, member: discord.Member, role: discord.Role) -> str:
    """Give ``member`` the PPE Player role (if missing) and mark them as a contest member."""
    already_had_role = role in member.roles
    if not already_had_role:
        await member.add_roles(role)
    await player_manager.add_player_to_contest(interaction, member.id)

    if already_had_role:
        return f"⚠️ `{member.display_name}` already has the `PPE Player` role."
    return f"✅ Added `{member.display_name}` to the PPE contest. They can now use PPE commands."


async def _add_to_team(interaction: discord.Interaction, member: discord.Member, team_name: str) -> str:
    """Add an existing PPE player to ``team_name`` and describe the outcome."""
    try:
        team, role_ok = await add_player_to_team_with_role(interaction, member, team_name)
    except ValueError as exc:
        return str(exc)

    message = f"✅ Added `{member.display_name}` to team **{team.name}**."
    if not role_ok:
        message += " ⚠️ I couldn't assign the team role (check my role hierarchy)."
    return message


async def command(
    interaction: discord.Interaction,
    member: discord.Member,
    team: str | None = None,
    *,
    team_name: str | None = None,
):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    role = ppe_player_role(interaction.guild)
    if not role:
        return await interaction.response.send_message("❌ PPE Player role not found. Create it first.")

    # Validate the team up front so a typo doesn't leave a half-finished change.
    target_team_query = team if team is not None else team_name
    resolved_team: str | None = None
    if target_team_query:
        resolved_team = resolve_team_name(await load_teams(interaction), target_team_query)
        if resolved_team is None:
            return await interaction.response.send_message(f"❌ Team `{target_team_query}` not found.", ephemeral=True)

    try:
        lines = [await _ensure_ppe_player(interaction, member, role)]
        if resolved_team:
            lines.append(await _add_to_team(interaction, member, resolved_team))
    except discord.Forbidden:
        return await interaction.response.send_message(
            "❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy."
        )
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

    await interaction.response.send_message("\n".join(lines))