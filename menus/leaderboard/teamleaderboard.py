import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import require_guild
from utils.team_manager import team_manager
from utils.team_contest_scoring import format_points_breakdown, load_team_contest_scoring


async def command(interaction: discord.Interaction):
    if await require_guild(interaction) is None:
        return

    try:
        leaderboard_data = await team_manager.get_team_leaderboard_data(interaction)
        scoring = await load_team_contest_scoring(interaction)

        rows = []
        for team_name, _leader_id, ppe_points, quest_points, total_points, member_count in leaderboard_data:
            breakdown = format_points_breakdown(
                ppe_points=ppe_points,
                quest_points=quest_points,
                total_points=total_points,
                include_quest_points=scoring.include_quest_points,
            )
            rows.append(
                f"**{team_name}**: {breakdown} pts ({member_count} members)"
            )

        await send_leaderboard(
            interaction,
            title="Team Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message="No teams available yet.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
