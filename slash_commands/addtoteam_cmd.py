"""Command to add a player to a team."""
import discord
from discord import app_commands
from dataclass import TeamData
from utils.player_records import load_player_records, load_teams, ensure_player_exists
from utils.team_manager import team_manager
from utils.autocomplete import team_name_autocomplete, target_user_ppe_id_autocomplete


async def command(
    interaction: discord.Interaction,
    team_name: str,
    player: discord.User | None = None,
    player_id: int | None = None,
):
    """Add a player to a team.
    
    Args:
        team_name: The name of the team to add the player to
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
            "❌ Please specify a player to add (mention, ID, or username).",
            ephemeral=True,
        )

    try:
        # Verify player exists in records and is a PPE member
        records = await load_player_records(interaction)
        player_key = ensure_player_exists(records, target_id)
        if player_key not in records or not records[player_key].is_member:
            return await interaction.response.send_message(
                "❌ Target player is not part of the PPE contest.",
                ephemeral=True,
            )

        # Check if player is already on a team
        player_data = records[player_key]
        if player_data.team_name:
            return await interaction.response.send_message(
                f"❌ Player is already on team `{player_data.team_name}`. Remove them first.",
                ephemeral=True,
            )

        # Add player to team
        team = await team_manager.add_player_to_team(interaction, target_id, team_name)
        
        # Assign team role if possible
        if interaction.guild:
            member = interaction.guild.get_member(target_id)
            role = discord.utils.get(interaction.guild.roles, name=team.name)
            if member and role and role not in member.roles:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass  # Continue even if role assignment fails

        await interaction.response.send_message(
            f"✅ Added <@{target_id}> to team **{team.name}**.",
            ephemeral=True,
        )

    except ValueError as exc:
        return await interaction.response.send_message(str(exc), ephemeral=True)
    except Exception as exc:
        return await interaction.response.send_message(f"❌ Error: {str(exc)}", ephemeral=True)
