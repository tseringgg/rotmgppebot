import discord

from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT
from utils.player_manager import player_manager
from utils.calc_points import calc_points


async def command(
        interaction: discord.Interaction,
        item_name: str,
        divine: bool = False,
        shiny: bool = False
    ):
    if item_name not in LOOT:
        return await interaction.response.send_message(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item.",
            ephemeral=True
        )
    
    try:
        points = calc_points(item_name, divine, shiny)
        final_key, points_added, active_ppe = await player_manager.add_loot_and_points(
            interaction, item_name, divine, shiny, points
        )
        embed = await build_loot_embed(active_ppe, recently_added=final_key)
        
        await interaction.response.send_message(
            content=f"> ✅ Added **{final_key}** to your active PPE for {points_added} points.",
            embed=embed, ephemeral=False
        )
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)