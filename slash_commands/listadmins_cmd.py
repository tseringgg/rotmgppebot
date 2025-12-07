import discord


async def list_admins(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        await interaction.response.send_message("❌ No 'PPE Admin' role found in this server.")
        return

    admins = [member.display_name for member in role.members]

    if not admins:
        await interaction.response.send_message("No Admins.")
        return

    admin_list = "\n".join(admins)
    await interaction.response.send_message(f"**PPE Admins:**\n{admin_list}")