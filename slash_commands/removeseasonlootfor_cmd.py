import discord
from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.loot_data import LOOT
from utils.quest_manager import remove_item_from_completed_quests


async def command(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False
    ):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    if item_name not in LOOT:
        return await interaction.response.send_message(
            f"❌ `{item_name}` is not a recognized item name.\n"
            f"Use the autocomplete suggestions to select a valid item.",
            ephemeral=True
        )
    
    try:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, user.id)
        
        # Check if target user is member
        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                f"❌ {user.display_name} is not part of the PPE contest.",
                ephemeral=True
            )
        
        player_data = records[key]
        
        # Remove from unique_items
        item_key = (item_name, shiny)
        
        # Check if exists
        if item_key not in player_data.unique_items:
            return await interaction.response.send_message(
                f"❌ **{item_name}{' (shiny)' if shiny else ''}** is not in {user.display_name}'s season loot collection!",
                ephemeral=True
            )
        
        player_data.unique_items.discard(item_key)
        removed_quest_entries = remove_item_from_completed_quests(player_data, item_name, shiny)
        
        await save_player_records(interaction, records)
        
        total_count = player_data.get_unique_item_count()
        
        response_lines = [
            f"✅ Removed **{item_name}{' (shiny)' if shiny else ''}** from {user.display_name}'s season loot!",
            f"They now have **{total_count}** unique items collected.",
        ]

        removed_entries = (
            removed_quest_entries.get("removed_completed_items", [])
            + removed_quest_entries.get("removed_completed_shinies", [])
            + removed_quest_entries.get("removed_completed_skins", [])
        )
        if removed_entries:
            response_lines.append(f"Removed completed quest entries: {', '.join(removed_entries)}")

        await interaction.response.send_message("\n".join(response_lines), ephemeral=False)
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
