

import discord


async def list_roles(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.")
        return
    roles = [r.name for r in interaction.guild.roles if r.name != "@everyone"]
    await interaction.response.send_message("🎭 Available roles:\n" + "\n".join(f"- {r}" for r in roles))