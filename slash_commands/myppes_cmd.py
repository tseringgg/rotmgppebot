


import discord
from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)
    key = interaction.user.id

    if key not in records or not records[key].ppes:
        return await interaction.response.send_message("❌ You don’t have any PPEs yet. Use `/newppe` to create one!")

    player_data = records[key]
    active_id = player_data.active_ppe
    # lines = [f"`{interaction.user.display_name}'s` PPEs:"]
    lines = []
    for ppe in sorted(player_data.ppes, key=lambda x: x.id):
        id_ = ppe.id
        pts = ppe.points  # ✅
        marker = " (Active)"
        pts_str = f"{int(pts)}" if pts == int(pts) else f"{pts:.1f}"

        if id_ == active_id:
            # Format points without decimal if whole number
            lines.append(f"**#{id_} {ppe.name}: {pts_str} points {marker}**")
        else:
            lines.append(f"*#{id_} {ppe.name}: {pts_str} points*")

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s PPEs",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    # for line in lines:
    #     embed.add_field(name="", value=line, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)  # public response