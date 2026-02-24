import discord
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction, class_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    records = await load_player_records(interaction)
    
    # Collect all characters of the specified class
    character_data = []
    for pid, data in records.items():
        # Skip non-members
        if not data.is_member:
            continue
        if not data.ppes:
            continue
        
        # Find all characters of the specified class
        for ppe in data.ppes:
            if str(ppe.name).lower() == class_name.lower():
                player = next((m.display_name for m in interaction.guild.members if m.id == pid), f"Unknown User ({pid})")
                character_data.append((player, ppe.id, ppe.points, pid))
    
    if not character_data:
        return await interaction.response.send_message(f"❌ No `{class_name}` characters found on the leaderboard.")
    
    # Sort by points descending
    character_data.sort(key=lambda x: x[2], reverse=True)
    
    # Build leaderboard message
    lines = [f"🏆 `{class_name} Leaderboard` 🏆"]
    for rank, (player, ppe_id, pts, pid) in enumerate(character_data, start=1):
        lines.append(f"{rank}. `{player.title()}` — PPE `#{ppe_id}`: `{pts:.1f}` points")
    
    await interaction.response.send_message("\n".join(lines))
