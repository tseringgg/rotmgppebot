import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_error_response, send_leaderboard
from menus.leaderboard.services import member_display_name, require_guild
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    guild = await require_guild(interaction)
    if guild is None:
        return
    try:
        records = await load_player_records(interaction)

        leaderboard_data = []
        for pid, data in records.items():
            if not data.is_member:
                continue
            ppes = getattr(data, "ppes", [])
            if not isinstance(ppes, list) or not ppes:
                continue

            best_ppe = max(ppes, key=lambda p: p.points)
            player = member_display_name(guild, pid)
            is_inactive = data.active_ppe != best_ppe.id
            leaderboard_data.append((player, best_ppe.name, best_ppe.points, is_inactive))

        leaderboard_data.sort(key=lambda x: x[2], reverse=True)

        rows = []
        for player, ppe_name, points, is_inactive in leaderboard_data:
            marker = " • (inactive)" if is_inactive else ""
            rows.append(f"**{player.title()}** — {ppe_name}: **{points:.1f}** pts{marker}")

        await send_leaderboard(
            interaction,
            title="PPE Leaderboard",
            entries=build_ranked_entry_lines(rows),
            color=discord.Color.gold(),
            empty_message="No PPE data available yet.\nPlayers can use `/newppe` to start competing.",
        )
    except Exception as e:
        await send_error_response(interaction, str(e))
