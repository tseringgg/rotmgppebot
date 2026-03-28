"""Command to remove a player from a team."""
import discord
from discord import app_commands
from dataclass import TeamData
from utils.player_records import load_player_records, load_teams, ensure_player_exists
from utils.team_manager import team_manager
from utils.autocomplete import team_name_autocomplete


async def command(
    interaction: discord.Interaction,
    team_name: str,
    player: discord.User | None = None,
    player_id: int | None = None,
):
    """Remove a player from a team.
    
    Args:
        team_name: The name of the team to remove the player from
        player: A Discord user (via mention or selection)
        player_id: The Discord ID of the player (alternative to player parameter)
    """
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    # Determine which player ID to use
    target_id = None
    if player:
        target_id = player.id
    elif player_id:
        target_id = player_id
    else:
        return await interaction.response.send_message(
            "❌ Please specify a player to remove (mention, ID, or username).",
            ephemeral=True,
        )

    try:
        # Remove player from team
        actual_name, removed_count, removed_ids, new_leader_id = await team_manager._remove_members_from_team(
            interaction,
            team_name=team_name,
            member_ids=[target_id],
        )

        if removed_count == 0:
            return await interaction.response.send_message(
                f"❌ Player is not on team **{actual_name}**.",
                ephemeral=True,
            )

        # Remove team role if possible
        if interaction.guild and removed_ids:
            team_role = discord.utils.get(interaction.guild.roles, name=actual_name)
            if team_role:
                for member_id in removed_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and team_role in member.roles:
                        try:
                            await member.remove_roles(team_role)
                        except discord.Forbidden:
                            pass  # Continue even if role removal fails

        leader_text = f" New leader: <@{new_leader_id}>." if new_leader_id else " Leader is now unassigned."
        await interaction.response.send_message(
            f"✅ Removed <@{target_id}> from **{actual_name}**.{leader_text}",
            ephemeral=True,
        )

    except ValueError as exc:
        return await interaction.response.send_message(str(exc), ephemeral=True)
    except Exception as exc:
        return await interaction.response.send_message(f"❌ Error: {str(exc)}", ephemeral=True)
