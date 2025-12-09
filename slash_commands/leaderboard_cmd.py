

import discord
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)

    # for m in interaction.guild.members:
    #     print(f"Member loaded: {m.display_name} (ID: {m.id})")

    leaderboard_data = []
    for pid, data in records.items():
        # if player is not a contest member, skip
        if not data.is_member:
            continue
        if not data.ppes:
            continue
        best_ppe = max(data.ppes, key=lambda p: p.points)
        if not len(interaction.guild.members):
            print("[WARN] Guild has no members loaded.")
        player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        leaderboard_data.append((player, best_ppe.name, best_ppe.points))

    leaderboard_data.sort(key=lambda x: x[2], reverse=True)

    # if leaderboard is empty
    if not leaderboard_data:
        return await interaction.response.send_message("❌ No PPE data available yet.")

    lines = ["🏆 `PPE Leaderboard` 🏆"]
    for rank, (player, ppe_id, pts) in enumerate(leaderboard_data, start=1):
        lines.append(f"{rank}. `{player.title()}` — `{ppe_id}`: `{pts:.1f}` points")

    await interaction.response.send_message("\n".join(lines))
