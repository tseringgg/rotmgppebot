import discord
from typing import Optional
from utils.player_records import load_player_records, ensure_player_exists
from utils.team_manager import team_manager


async def command(interaction: discord.Interaction, team_name: Optional[str] = None):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        # Determine which team to show
        target_team = team_name
        
        if not target_team:
            # Get user's team from player records
            records = await load_player_records(interaction)
            user_key = ensure_player_exists(records, interaction.user.id)
            
            if user_key not in records or not records[user_key].team_name:
                return await interaction.response.send_message("❌ You are not on a team. Use `/myteam [team_name]` to see a specific team.")
            
            target_team = records[user_key].team_name
        
        # Get team members info
        team_info = await team_manager.get_team_members_info(interaction, target_team)
        
        if not team_info:
            return await interaction.response.send_message(f"❌ Team `{target_team}` not found.")
        
        team_name_result, leader_id, members_info = team_info
        
        if not members_info:
            return await interaction.response.send_message(f"❌ Team `{team_name_result}` has no active members with PPE characters.")
        
        # Sort members by points descending
        members_info_sorted = sorted(members_info, key=lambda x: x[2], reverse=True)
        
        # Build the message
        lines = [f"🏆 **Team: `{team_name_result}`** 🏆"]
        lines.append("")
        
        total_points = 0
        for rank, (member_id, member_name, points, ppe_class) in enumerate(members_info_sorted, start=1):
            lines.append(f"{rank}. `{member_name}` — `{points:.1f}` pts (`{ppe_class}`)")
            total_points += points
        
        lines.append("")
        lines.append(f"**Total Team Points:** `{total_points:.1f}`")
        
        await interaction.response.send_message("\n".join(lines))
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
