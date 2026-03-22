import discord

from utils.player_records import load_player_records
from utils.pagination import chunk_lines_to_pages, LootPaginationView


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

    records = await load_player_records(interaction)

    leaderboard_data = []
    for pid, data in records.items():
        if not data.is_member:
            continue

        completed_count = (
            len(data.quests.completed_items)
            + len(data.quests.completed_shinies)
            + len(data.quests.completed_skins)
        )
        if completed_count <= 0:
            continue

        player_name = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        leaderboard_data.append((player_name, completed_count))

    leaderboard_data.sort(key=lambda x: x[1], reverse=True)

    if not leaderboard_data:
        return await interaction.response.send_message(
            "No quest completions recorded yet.\n"
            "Players can use /myquests and complete objectives to appear here.",
            ephemeral=True,
        )

    lines = ["**Quest Completion Leaderboard**", ""]
    for rank, (player_name, completed_count) in enumerate(leaderboard_data, start=1):
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."
        lines.append(f"{medal} **{player_name}** — {completed_count} quests completed")

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
