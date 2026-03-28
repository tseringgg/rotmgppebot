import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_leaderboard
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)

    leaderboard_data = []
    for pid, data in records.items():
        if not data.is_member:
            continue
        if not data.ppes:
            continue
        best_ppe = max(data.ppes, key=lambda p: p.points)
        if not len(interaction.guild.members):
            print("[WARN] Guild has no members loaded.")
        player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        is_inactive = data.active_ppe != best_ppe.id
        leaderboard_data.append((player, best_ppe.name, best_ppe.points, is_inactive))

    leaderboard_data.sort(key=lambda x: x[2], reverse=True)

    if not leaderboard_data:
        return await interaction.response.send_message("❌ No PPE data available yet.")

    rows = []
    for player, ppe_name, points, is_inactive in leaderboard_data:
        marker = " • (inactive)" if is_inactive else ""
        rows.append(f"**{player.title()}** — {ppe_name}: **{points:.1f}** pts{marker}")
    entries = build_ranked_entry_lines(rows)

    await send_leaderboard(
        interaction,
        title="PPE Leaderboard",
        entries=entries,
        color=discord.Color.gold(),
    )
