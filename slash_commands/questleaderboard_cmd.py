import discord

from utils.player_records import load_player_records
from utils.pagination import chunk_lines_to_pages, LootPaginationView
from utils.guild_config import get_quest_points


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

    lines = [
        "**Quest Points Leaderboard**",
        f"`Reg {regular_points} | Shiny {shiny_points} | Skin {skin_points}`",
        "",
    ]
    for rank, (player_name, completed_regular, completed_shiny, completed_skin, total_points) in enumerate(leaderboard_data, start=1):
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."
        lines.append(
            f"{medal} **{player_name}** — {completed_regular} Reg, {completed_shiny} Shiny, {completed_skin} Skin • **{total_points} pts**"
        )

    pages = chunk_lines_to_pages(lines, 3900)
    embeds = []
    for page_num, page_lines in enumerate(pages, start=1):
        embed = discord.Embed(
            title="Quest Leaderboard",
            description="\n".join(page_lines),
            color=discord.Color.gold(),
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page {page_num}/{len(pages)}")
        embeds.append(embed)

    if len(embeds) == 1:
        await interaction.response.send_message(embed=embeds[0])
    else:
        view = LootPaginationView(embeds=embeds, user_id=interaction.user.id)
        await interaction.response.send_message(embed=embeds[0], view=view)
