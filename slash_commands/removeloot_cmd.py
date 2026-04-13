

import discord

from utils.loot_data import LOOT
from utils.loot_ops import (
    format_ppe_remove_message,
    remove_ppe_loot,
    send_ppe_markdown_followup,
    validate_loot_input,
)
from utils.player_records import get_active_ppe_of_user


async def command(
        interaction: discord.Interaction,
        item_name: str,
        rarity: str,
        shiny: bool = False
    ):
    try:
        validate_loot_input(item_name, shiny=shiny, known_items=LOOT)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        rarity_normalized = rarity.lower().strip()
        ppe_id = (await get_active_ppe_of_user(interaction)).id
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise ValueError("❌ Could not retrieve your member information.")
        result = await remove_ppe_loot(
            interaction,
            user=user,
            ppe_id=ppe_id,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity_normalized,
        )
        
        await interaction.response.send_message(
            content=format_ppe_remove_message(result),
            ephemeral=False
        )
        await send_ppe_markdown_followup(interaction, ppe=result.ppe, ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)