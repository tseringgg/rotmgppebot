import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.team_contest_scoring import compute_ppe_points, get_best_ppe, load_team_contest_scoring
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return
    try:
        records = await load_player_records(interaction)
        scoring = await load_team_contest_scoring(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue
            ppes = getattr(data, "ppes", [])
            if not isinstance(ppes, list) or not ppes:
                continue

            player = member_display_name(guild, pid)
            points = compute_ppe_points(data, aggregate=scoring.ppe_aggregate_points)
            best_ppe = get_best_ppe(data)
            leaderboard_data.append((player, best_ppe, points, len(ppes), data.active_ppe))

        leaderboard_data.sort(key=lambda x: x[2], reverse=True)

        rows = []
        for player, best_ppe, points, ppe_count, active_ppe_id in leaderboard_data:
            if scoring.ppe_aggregate_points:
                count_label = "character" if ppe_count == 1 else "characters"
                rows.append(f"**{player.title()}** — All PPEs ({ppe_count} {count_label}): **{points:.1f}** pts")
                continue

            if best_ppe is None:
                continue

            is_inactive = active_ppe_id != best_ppe.id
            marker = " • (inactive)" if is_inactive else ""
            rows.append(f"**{player.title()}** — {best_ppe.name}: **{points:.1f}** pts{marker}")

        await send_leaderboard(
            interaction,
            title="PPE Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message="No PPE data available yet.\nPlayers can use `/newppe` to start competing.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
