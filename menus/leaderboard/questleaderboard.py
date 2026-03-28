import discord

from utils.guild_config import get_quest_points
from menus.leaderboard.common import build_ranked_entry_lines, send_leaderboard
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    records = await load_player_records(interaction)
    regular_points, shiny_points, skin_points = await get_quest_points(interaction)

    leaderboard_data = []
    for pid, data in records.items():
        if not data.is_member:
            continue

        completed_regular = len(data.quests.completed_items)
        completed_shiny = len(data.quests.completed_shinies)
        completed_skin = len(data.quests.completed_skins)

        total_completed = completed_regular + completed_shiny + completed_skin
        total_points = (
            completed_regular * regular_points
            + completed_shiny * shiny_points
            + completed_skin * skin_points
        )

        if total_completed <= 0 and total_points <= 0:
            continue

        player_name = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        leaderboard_data.append((player_name, completed_regular, completed_shiny, completed_skin, total_points))

    leaderboard_data.sort(key=lambda x: (x[4], x[1] + x[2] + x[3]), reverse=True)

    if not leaderboard_data:
        return await interaction.response.send_message(
            "No quest completions recorded yet.\n"
            "Players can use /myquests and complete objectives to appear here.",
            ephemeral=True,
        )

    rows = []
    for player_name, completed_regular, completed_shiny, completed_skin, total_points in leaderboard_data:
        rows.append(
            f"**{player_name}** — {completed_regular} Reg, {completed_shiny} Shiny, {completed_skin} Skin • **{total_points} pts**"
        )

    await send_leaderboard(
        interaction,
        title="Quest Leaderboard",
        entries=build_ranked_entry_lines(rows),
        color=discord.Color.gold(),
        header_lines=[f"Reg {regular_points} | Shiny {shiny_points} | Skin {skin_points}"],
    )
