import discord

from utils.loot_data import LOOT
from utils.loot_ops import (
    format_season_remove_message,
    normalize_rarity,
    remove_season_loot,
    send_season_markdown_followup,
    validate_loot_input,
)


async def command(
        interaction: discord.Interaction,
        item_name: str,
        shiny: bool = False,
        rarity: str = "common"
    ):
    rarity = normalize_rarity(rarity)
    try:
        validate_loot_input(item_name, shiny=shiny, known_items=LOOT)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        result = await remove_season_loot(
            interaction,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity,
        )

        response_lines = [format_season_remove_message(result)]

        removed_entries = (
            result.quest_update.get("removed_completed_items", [])
            + result.quest_update.get("removed_completed_shinies", [])
            + result.quest_update.get("removed_completed_skins", [])
        )
        if removed_entries:
            response_lines.append(f"🧹 Removed completed quest entries: {', '.join(removed_entries)}")

        await interaction.response.send_message("\n".join(response_lines), ephemeral=False)
        await send_season_markdown_followup(
            interaction,
            player_data=result.player_data,
            display_name=interaction.user.display_name,
            ephemeral=True,
        )
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
