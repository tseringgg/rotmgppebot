

import discord

from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT
from utils.player_manager import player_manager
from utils.calc_points import calc_points
from utils.player_records import get_active_ppe_of_user


async def command(
        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
    # if item_name not in LOOT:
    #     return await interaction.response.send_message(
    #         f"❌ `{item_name}` is not a recognized item name.\n"
    #         f"Use the autocomplete suggestions to select a valid item.",
    #         ephemeral=True
    #     )
    
    try:
        points = calc_points(item_name, divine, shiny)
        ppe_id = (await get_active_ppe_of_user(interaction)).id
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise ValueError("❌ Could not retrieve your member information.")
        final_key, points_removed, active_ppe = await player_manager.remove_loot_and_points(
            interaction, user=user, ppe_id=ppe_id, item_name=item_name, divine=divine, shiny=shiny, points=points
        )
        embed = await build_loot_embed(active_ppe, recently_added=item_name)
        
        await interaction.response.send_message(
            content=f"> 🗑️ Removed **1x {final_key}** from your active PPE and took away {points_removed} points.",
            embed=embed, ephemeral=False
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)