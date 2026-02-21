import discord
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Get team leaderboard data
        leaderboard_data = await team_manager.get_team_leaderboard_data(interaction)
        
        if not leaderboard_data:
            return await interaction.response.send_message("❌ No teams available yet.")
        
        lines = ["🏆 `Team Leaderboard` 🏆"]
        for rank, (team_name, leader_id, total_points, member_count) in enumerate(leaderboard_data, start=1):
            lines.append(f"{rank}. `{team_name}` — `{total_points:.1f}` points (`{member_count}` members)")
        
        await interaction.response.send_message("\n".join(lines))
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
