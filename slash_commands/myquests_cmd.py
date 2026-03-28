import discord

from menus.myquests import open_myquests_menu


async def command(interaction: discord.Interaction):
    try:
        await open_myquests_menu(interaction, ephemeral=False)
    except (ValueError, KeyError, LookupError) as e:
        if not interaction.response.is_done():
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.followup.send(str(e), ephemeral=True)
