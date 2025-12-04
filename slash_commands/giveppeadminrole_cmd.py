

import discord


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        await interaction.response.send_message("❌ PPE Admin role not found. Create it first.")
        return

    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Gave `PPE Admin` role to `{member.display_name}`.")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.")
