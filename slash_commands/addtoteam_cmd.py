"""Command to add a player to a team."""
import discord
from utils.player_records import load_player_records, ensure_player_exists
from utils.team_membership import add_player_to_team_with_role


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

        # Add player to team and assign the team role if possible
        team, _role_ok = await add_player_to_team_with_role(interaction, target_id, team_name)

        await interaction.response.send_message(
            f"✅ Added <@{target_id}> to team **{team.name}**.",
            ephemeral=True,
        )

    except ValueError as exc:
        return await interaction.response.send_message(str(exc), ephemeral=True)
    except Exception as exc:
        return await interaction.response.send_message(f"❌ Error: {str(exc)}", ephemeral=True)
