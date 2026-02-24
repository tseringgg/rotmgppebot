import discord
from utils.player_records import load_player_records, ensure_player_exists


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, member.id)
    
    if key not in records or not records[key].ppes:
        return await interaction.response.send_message(f"❌ `{member.display_name}` has no PPE characters.")
    
    player_data = records[key]
    
    # Build character list
    lines = [f"📜 `{member.display_name}'s Characters:`"]
    
    # Sort by ID for consistency
    ppes = sorted(player_data.ppes, key=lambda p: p.id)
    
    for ppe in ppes:
        active_marker = " ✓" if player_data.active_ppe == ppe.id else ""
        lines.append(f"PPE `#{ppe.id}` — `{ppe.name}`: `{ppe.points:.1f}` points{active_marker}")
    
    await interaction.response.send_message("\n".join(lines))
