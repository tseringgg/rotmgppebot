


import discord

from utils.player_records import load_player_records


async def command(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    records = await load_player_records(interaction)

    # Get all members who are marked as PPE participants
    members = [(name, data) for name, data in records.items() if data.is_member]

    if not members:
        return await interaction.response.send_message("❌ No one has been added to the PPE contest yet.")

    lines = ["`🏆 Current PPE Contest Participants 🏆`"]
    for id, data in members:
        display_name = next((x.display_name for x in interaction.guild.members if x.id == id), f"Unknown User ({id})")
        ppe_count = len(data.ppes)
        active_id = data.active_ppe if data.active_ppe is not None else "None"
        lines.append(f"• `{display_name}` — {ppe_count} PPE(s), Active: PPE #{active_id}")

    await interaction.response.send_message("\n".join(lines))