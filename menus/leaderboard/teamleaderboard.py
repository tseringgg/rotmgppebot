import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_leaderboard
from utils.team_manager import team_manager
from utils.team_contest_scoring import format_points_breakdown, load_team_contest_scoring


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        leaderboard_data = await team_manager.get_team_leaderboard_data(interaction)
        scoring = await load_team_contest_scoring(interaction)

        if not leaderboard_data:
            return await interaction.response.send_message("❌ No teams available yet.")

        rows = []
        for team_name, _leader_id, ppe_points, quest_points, total_points, member_count in leaderboard_data:
            breakdown = format_points_breakdown(
                ppe_points=ppe_points,
                quest_points=quest_points,
                total_points=total_points,
                include_quest_points=scoring.include_quest_points,
            )
            rows.append(
                f"**{team_name}** — {breakdown} pts ({member_count} members)"
            )

        await send_leaderboard(
            interaction,
            title="Team Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
        )
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
