import discord

from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT
from utils.helpers.loot_table_message import LootTableMessage
from utils.player_manager import player_manager
from utils.points_service import calculate_drop_points, has_item_variant
from utils.player_records import get_active_ppe_of_user


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
    
    # Validate that shiny variant exists in database
    if shiny:
        if not has_item_variant(item_name, shiny=True):
            return await interaction.response.send_message(
                f"❌ Shiny variant of `{item_name}` is not currently in bot.",
                ephemeral=True
            )
    
    try:
        points = calculate_drop_points(item_name, divine, shiny)
        ppe_id = (await get_active_ppe_of_user(interaction)).id
        user = interaction.user
        if not isinstance(user, discord.Member):
            raise ValueError("❌ Could not retrieve your member information.")
        final_key, points_added, active_ppe, quest_update = await player_manager.add_loot_and_points(
            interaction, user=user, ppe_id=ppe_id, item_name=item_name, divine=divine, shiny=shiny, points=points
        )
        display_item_name = final_key
        if shiny:
            display_item_name = f"Shiny {display_item_name}"
        if divine:
            display_item_name = f"Divine {display_item_name}"

        quest_lines = []
        for completed_item in quest_update.get("completed_items", []):
            quest_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_shiny in quest_update.get("completed_shinies", []):
            quest_lines.append(f"✨ Shiny quest completed: **{completed_shiny}**")
        for completed_skin in quest_update.get("completed_skins", []):
            quest_lines.append(f"✅ Skin quest completed: **{completed_skin}**")

        if quest_lines:
            quest_lines.append("Use `/myquests` to view your updated quest list.")
        
        # Use LootTableMessage to handle response + embed followup
        loot_message = LootTableMessage(
            interaction=interaction,
            message_type="markdown",
            response=f"> ✅ Added **{display_item_name}** to your active PPE for {points_added} points.",
            response_ephemeral=False,
            ephemeral=True,
            embed_content=f"Your active PPE now has **{active_ppe.points} total points**."
        )
        
        await loot_message.send_player_loot(
            active_ppe, 
            user_id=user.id, 
            recently_added=final_key
        )

        if quest_lines:
            await interaction.followup.send("\n".join(quest_lines), ephemeral=True)
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
