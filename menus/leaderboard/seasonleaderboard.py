import discord

from menus.leaderboard.common import build_ranked_entry_lines, send_leaderboard
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    records = await load_player_records(interaction)

    leaderboard_data = []
    for pid, data in records.items():
        if not data.is_member:
            continue

        unique_count = data.get_unique_item_count()

        if unique_count == 0:
            continue

        player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        leaderboard_data.append((player, unique_count))

    leaderboard_data.sort(key=lambda x: x[1], reverse=True)

    if not leaderboard_data:
        return await interaction.response.send_message(
            "No season loot data available yet!\n"
            "Players can use `/addseasonloot` to start tracking unique items.",
            ephemeral=True,
        )

    rows = [f"**{player}** — {count} unique items" for player, count in leaderboard_data]
    await send_leaderboard(
        interaction,
        title="Season Loot Leaderboard",
        entries=build_ranked_entry_lines(rows),
        color=discord.Color.gold(),
    )
