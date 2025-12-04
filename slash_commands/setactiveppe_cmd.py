

import discord

from utils.player_records import ensure_player_exists, get_active_ppe, load_player_records, save_player_records


async def command(interaction: discord.Interaction, ppe_id: int):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]

    ppe_ids = [ppe.id for ppe in player_data.ppes]
    if ppe_id not in ppe_ids:
        return await interaction.response.send_message(f"❌ You don’t have a PPE #{ppe_id}. Use `/newppe` to create one.")

    player_data.active_ppe = ppe_id
    active_ppe = get_active_ppe(player_data)
    if not active_ppe:
        return await interaction.response.send_message("❌ Could not find your active PPE record. Try creating a new one with `/newppe`.")
    await save_player_records(interaction=interaction, records=records)
    # await interaction.response.send_message(f"> ✅ Set **PPE #{ppe_id}** ({active_ppe.name}) as your active PPE.")

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

    await interaction.response.send_message(content=f"> ✅ Set **PPE #{ppe_id}** ({active_ppe.name}) as your active PPE.",
                                    embed=embed, ephemeral=False)  # public response