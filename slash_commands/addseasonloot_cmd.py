import discord

from utils.loot_data import LOOT
from utils.loot_ops import (
    add_season_loot,
    format_season_add_message,
    normalize_rarity,
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
        result = await add_season_loot(
            interaction,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity,
        )

        response_lines = [format_season_add_message(result)]
        for completed_item in result.quest_update.get("completed_items", []):
            response_lines.append(f"✅ Item quest completed: **{completed_item}**")
        for completed_shiny in result.quest_update.get("completed_shinies", []):
            response_lines.append(f"✨ Shiny quest completed: **{completed_shiny}**")
        for completed_skin in result.quest_update.get("completed_skins", []):
            response_lines.append(f"✅ Skin quest completed: **{completed_skin}**")
        if result.quest_update.get("completed_items") or result.quest_update.get("completed_shinies") or result.quest_update.get("completed_skins"):
            response_lines.append("Use `/myquests` to view your updated quest list.")

        await interaction.response.send_message("\n".join(response_lines), ephemeral=False)
        await send_season_markdown_followup(
            interaction,
            player_data=result.player_data,
            display_name=interaction.user.display_name,
            ephemeral=True,
        )
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
