import discord
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    records = await load_player_records(interaction)
    
    # Build leaderboard data
    leaderboard_data = []
    for pid, data in records.items():
        # Only include contest members
        if not data.is_member:
            continue
        
        unique_count = data.get_unique_item_count()
        
        # Skip players with no unique items
        if unique_count == 0:
            continue
        
        # Get player display name
        player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
        leaderboard_data.append((player, unique_count))
    
    # Sort by unique item count (descending)
    leaderboard_data.sort(key=lambda x: x[1], reverse=True)
    
    # If leaderboard is empty
    if not leaderboard_data:
        return await interaction.response.send_message(
            "No season loot data available yet!\n"
            "Players can use `/addseasonloot` to start tracking unique items.",
            ephemeral=True
        )
    
    # Build leaderboard message
    lines = ["**Season Loot Leaderboard**\n"]
    
    for rank, (player, count) in enumerate(leaderboard_data, start=1):
        # Add medal emojis for top 3
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."
        
        lines.append(f"{medal} **{player}** — {count} unique items")
    
    embed = discord.Embed(
        title="Season Loot Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    
    await interaction.response.send_message(embed=embed)
