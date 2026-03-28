import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_leaderboard
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        leaderboard_data = await team_manager.get_team_leaderboard_data(interaction)

        if not leaderboard_data:
            return await interaction.response.send_message("❌ No teams available yet.")

        rows = []
        for team_name, _leader_id, ppe_points, quest_points, total_points, member_count in leaderboard_data:
            rows.append(
                f"**{team_name}** — {ppe_points:.1f} PPE + {quest_points} Quest = **{total_points:.1f}** pts ({member_count} members)"
            )

        await send_leaderboard(
            interaction,
            title="Team Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
        )
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
