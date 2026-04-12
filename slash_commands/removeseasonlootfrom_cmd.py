import discord
from utils.player_records import load_player_records, save_player_records, ensure_player_exists
from utils.loot_data import LOOT
from utils.guild_config import get_quest_targets, load_guild_config
from utils.quest_manager import refresh_player_quests, remove_item_from_completed_quests
from utils.season_loot_history import normalize_rarity, remove_season_item_log, unique_season_item_count


async def command(
        interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    rarity = normalize_rarity(rarity)
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
        
        removed = remove_season_item_log(
            player_data,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity,
            remove_all=False,
        )

        if removed <= 0:
            return await interaction.response.send_message(
                f"❌ **{item_name}{' (shiny)' if shiny else ''} [{rarity}]** is not in {user.display_name}'s season loot collection!",
                ephemeral=True
            )

        removed_quest_entries = remove_item_from_completed_quests(player_data, item_name, shiny)

        regular_target, shiny_target, skin_target = await get_quest_targets(interaction)
        config = await load_guild_config(interaction)
        refresh_player_quests(
            player_data,
            target_item_quests=regular_target,
            target_shiny_quests=shiny_target,
            target_skin_quests=skin_target,
            global_quests={
                "enabled": bool(config["quest_settings"].get("use_global_quests", False)),
                "regular": list(config["quest_settings"].get("global_regular_quests", [])),
                "shiny": list(config["quest_settings"].get("global_shiny_quests", [])),
                "skin": list(config["quest_settings"].get("global_skin_quests", [])),
            },
        )
        
        await save_player_records(interaction, records)
        
        total_count = unique_season_item_count(player_data)
        
        response_lines = [
            f"✅ Removed **{item_name}{' (shiny)' if shiny else ''} [{rarity}]** from {user.display_name}'s season loot!",
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
