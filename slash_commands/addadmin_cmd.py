import discord


async def command(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name="PPE Admin")
    if not role:
        await interaction.response.send_message("❌ PPE Admin role not found. Create it first.", ephemeral=True)
        return

    if role in member.roles:
        await interaction.response.send_message(f"⚠️ `{member.display_name}` already has the `PPE Admin` role.")
        return

    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Added `{member.display_name}` as PPE Admin.")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to manage that role. Move my bot role higher in the hierarchy.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(str(e), ephemeral=True)