import discord
from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.loot_data import LOOT
from utils.calc_points import load_loot_points
from utils.quest_manager import update_quests_for_item
from utils.guild_config import get_quest_targets


async def command(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False
    ):
    display_item_name = f"Shiny {item_name}" if shiny else item_name

    if item_name not in LOOT:
        return await interaction.response.send_message(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item.",
            ephemeral=True
        )
    
    # Validate that shiny variant exists in database
    if shiny:
        loot_points = load_loot_points()
        shiny_item_name = f"{item_name} (shiny)"
        if shiny_item_name not in loot_points:
            return await interaction.response.send_message(
                f"❌ Shiny variant of `{item_name}` is not currently in bot.",
                ephemeral=True
            )
    
    try:
        records = await load_player_records(interaction)
        user_id = interaction.user.id
        key = ensure_player_exists(records, user_id)
        
        # Check if user is member
        if key not in records or not records[key].is_member:
            raise KeyError("❌ You're not part of the PPE contest.")
        
        player_data = records[key]
        
        # Add to unique_items
        item_key = (item_name, shiny)
        
        # Check if already exists
        if item_key in player_data.unique_items:
            return await interaction.response.send_message(
                f"⚠️ **{display_item_name}** is already in your season loot collection!",
                ephemeral=True
            )
        
        player_data.unique_items.add(item_key)

        regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
        quest_update = update_quests_for_item(
            player_data,
            item_name,
            shiny,
            target_item_quests=regular_target,
            target_shiny_quests=shiny_target,
            target_skin_quests=skin_target,
        )
        
        await save_player_records(interaction, records)
        
        total_count = player_data.get_unique_item_count()
        
        response_lines = [
            f"✅ Added **{display_item_name}** to your season loot!\n"
            f"You now have **{total_count}** unique items collected."
        ]

        for completed_item in quest_update.get("completed_items", []):
            response_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_shiny in quest_update.get("completed_shinies", []):
            response_lines.append(f"✨ Shiny quest completed: **{completed_shiny}**")
        for completed_skin in quest_update.get("completed_skins", []):
            response_lines.append(f"✅ Skin quest completed: **{completed_skin}**")
        if quest_update.get("completed_items") or quest_update.get("completed_shinies") or quest_update.get("completed_skins"):
            response_lines.append("Use `/myquests` to view your updated quest list.")

        await interaction.response.send_message("\n".join(response_lines), ephemeral=False)
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
