import discord

from utils.player_records import load_player_records, ensure_player_exists
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
        user: discord.Member,
        item_name: str,
    shiny: bool = False,
    rarity: str = "common"
    ):
    rarity = normalize_rarity(rarity)
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    try:
        validate_loot_input(item_name, shiny=shiny, known_items=LOOT)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    try:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, user.id)
        
        # Check if target user is member
        if key not in records or not records[key].is_member:
            return await interaction.response.send_message(
                f"❌ {user.display_name} is not part of the PPE contest.",
                ephemeral=True
            )
        
        result = await add_season_loot(
            interaction,
            user_id=user.id,
            username=user.display_name,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity,
        )
        await interaction.response.send_message(format_season_add_message(result), ephemeral=False)
        await send_season_markdown_followup(
            interaction,
            player_data=result.player_data,
            display_name=user.display_name,
            ephemeral=True,
        )
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
