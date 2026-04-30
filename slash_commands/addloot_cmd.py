import discord
import os

from utils.loot_data import LOOT
from utils.image_utils import overlay_rarity_badge, resolve_item_image_path
from utils.loot_ops import (
    add_ppe_loot,
    format_ppe_add_message,
    send_ppe_markdown_followup,
    validate_loot_input,
)
from utils.player_records import get_active_ppe_of_user


async def command(
        interaction: discord.Interaction,
        item_name: str,
    shiny: bool = False,
    rarity: str = "common",
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
        result = await add_ppe_loot(
            interaction,
            user=user,
            ppe_id=ppe_id,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity_normalized,
        )

        # Message is fully formatted by `format_ppe_add_message`, which includes points, quests/sets and timestamp.
        
        image_file: discord.File | None = None
        overlay_path: str | None = None
        image_path = resolve_item_image_path(item_name, shiny=shiny)
        if image_path:
            overlay_path = overlay_rarity_badge(image_path, rarity_normalized)
            file_path = overlay_path or image_path
            image_file = discord.File(file_path)
        standardized = format_ppe_add_message(result)

        try:
            await interaction.response.send_message(standardized, file=image_file, ephemeral=False)
            await send_ppe_markdown_followup(interaction, ppe=result.ppe, ephemeral=True)
        finally:
            if overlay_path and image_path and overlay_path != image_path and os.path.exists(overlay_path):
                os.remove(overlay_path)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
