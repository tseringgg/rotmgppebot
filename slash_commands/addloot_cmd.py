import discord
import os

from utils.loot_data import LOOT
from utils.helpers.loot_table_message import LootTableMessage
from utils.image_utils import overlay_rarity_badge, resolve_item_image_path
from utils.player_manager import player_manager
from utils.points_service import calculate_drop_points, has_item_variant
from utils.guild_config import load_guild_config
from utils.player_records import get_active_ppe_of_user


async def command(
        interaction: discord.Interaction,
        item_name: str,
    shiny: bool = False,
    rarity: str = "common",
    ):
    if item_name not in LOOT:
        return await interaction.response.send_message(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item.",
            ephemeral=True
        )
    
    # Validate that shiny variant exists in database
    if shiny:
        if not has_item_variant(item_name, shiny=True):
            return await interaction.response.send_message(
                f"❌ Shiny variant of `{item_name}` is not currently in bot.",
                ephemeral=True
            )
    
    try:
        rarity_normalized = rarity.lower().strip()
        divine = rarity_normalized == "divine"

        guild_config = await load_guild_config(interaction)
        points = calculate_drop_points(item_name, divine, shiny, rarity=rarity_normalized, guild_config=guild_config)
        ppe_id = (await get_active_ppe_of_user(interaction)).id
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise ValueError("❌ Could not retrieve your member information.")
        final_key, points_added, active_ppe, quest_update = await player_manager.add_loot_and_points(
            interaction,
            user=user,
            ppe_id=ppe_id,
            item_name=item_name,
            divine=divine,
            shiny=shiny,
            rarity=rarity_normalized,
            points=points,
        )
        display_item_name = final_key
        if shiny:
            display_item_name = f"Shiny {display_item_name}"
        if divine:
            display_item_name = f"Divine {display_item_name}"
        if rarity_normalized != "common" and not (divine and rarity_normalized == "divine"):
            display_item_name = f"{rarity_normalized.title()} {display_item_name}"

        quest_lines = []
        for completed_item in quest_update.get("completed_items", []):
            quest_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_shiny in quest_update.get("completed_shinies", []):
            quest_lines.append(f"✨ Shiny quest completed: **{completed_shiny}**")
        for completed_skin in quest_update.get("completed_skins", []):
            quest_lines.append(f"✅ Skin quest completed: **{completed_skin}**")

        if quest_lines:
            quest_lines.append("Use `/myquests` to view your updated quest list.")
        
        image_file: discord.File | None = None
        overlay_path: str | None = None
        image_path = resolve_item_image_path(item_name, shiny=shiny)
        if image_path:
            overlay_path = overlay_rarity_badge(image_path, rarity_normalized)
            file_path = overlay_path or image_path
            image_file = discord.File(file_path)

        loot_message = LootTableMessage(
            interaction=interaction,
            message_type="markdown",
            response=f"> ✅ Added **{display_item_name}** to your active PPE for {points_added} points.",
            response_ephemeral=False,
            response_file=image_file,
            ephemeral=True,
            embed_content=f"Your active PPE now has **{active_ppe.points} total points**."
        )

        try:
            await loot_message.send_player_loot(
                active_ppe,
                user_id=user.id,
                recently_added=final_key,
            )
        finally:
            if overlay_path and image_path and overlay_path != image_path and os.path.exists(overlay_path):
                os.remove(overlay_path)

        if quest_lines:
            await interaction.followup.send("\n".join(quest_lines), ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
