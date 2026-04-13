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

        quest_lines = []
        for completed_item in result.quest_update.get("completed_items", []):
            quest_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_shiny in result.quest_update.get("completed_shinies", []):
            quest_lines.append(f"✨ Shiny quest completed: **{completed_shiny}**")
        for completed_skin in result.quest_update.get("completed_skins", []):
            quest_lines.append(f"✅ Skin quest completed: **{completed_skin}**")

        # Add set completion messages
        set_lines = []
        if result.newly_completed_sets:
            for set_name, set_type in result.newly_completed_sets:
                set_lines.append(f"🎉 **Set Completed!** {set_name} ({set_type})")

        if quest_lines:
            quest_lines.append("Use `/myquests` to view your updated quest list.")
        
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

        # Send set completion messages first (higher priority)
        if set_lines:
            await interaction.followup.send("\n".join(set_lines), ephemeral=False)

        # Then send quest completion messages
        if quest_lines:
            await interaction.followup.send("\n".join(quest_lines), ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
