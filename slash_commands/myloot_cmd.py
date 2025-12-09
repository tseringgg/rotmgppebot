

import discord

from utils.embed_builders import build_loot_embed
from utils.player_records import get_active_ppe_of_user


async def command(interaction: discord.Interaction):
    try:
        active_ppe = await get_active_ppe_of_user(interaction)
        embed = await build_loot_embed(active_ppe)
    except (ValueError, KeyError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)

    await interaction.response.send_message(embed=embed, ephemeral=True) # public response, not ephemeral