import discord
import os

from utils.player_records import ensure_player_exists, load_player_records
from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT
from utils.image_utils import overlay_rarity_badge, resolve_item_image_path
from utils.loot_ops import (
    add_ppe_loot,
    format_ppe_add_message,
    send_ppe_markdown_followup,
    validate_loot_input,
)

async def command(interaction: discord.Interaction, user: discord.Member, id: int, item_name: str, shiny: bool = False, rarity: str = "common"):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    try:
        validate_loot_input(item_name, shiny=shiny, known_items=LOOT)
    except ValueError as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
    
    # Load player records
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, user.id)
    player_data = records[key]
    
    # Check if target player has any PPEs
    if not player_data.ppes:
        return await interaction.response.send_message(
            f"❌ {user.display_name} doesn't have any PPEs.",
            ephemeral=True
        )
    
    # Find the specific PPE by ID
    target_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == id:
            target_ppe = ppe
            break
    
    if not target_ppe:
        return await interaction.response.send_message(
            f"❌ Could not find PPE #{id} for {user.display_name}.",
            ephemeral=True
        )
    
    try:
        rarity_normalized = rarity.lower().strip()
        result = await add_ppe_loot(
            interaction,
            user=user,
            ppe_id=id,
            item_name=item_name,
            shiny=shiny,
            rarity=rarity_normalized,
        )
        
        # Build embed
        embed = await build_loot_embed(result.ppe, user_id=user.id, recently_added=item_name)
        
        response_file: discord.File | None = None
        overlay_path: str | None = None
        image_path = resolve_item_image_path(item_name, shiny=shiny)
        if image_path:
            overlay_path = overlay_rarity_badge(image_path, rarity_normalized)
            response_file = discord.File(overlay_path or image_path)

        await interaction.response.send_message(format_ppe_add_message(result), file=response_file)
        await send_ppe_markdown_followup(interaction, ppe=result.ppe, ephemeral=True)
        await interaction.followup.send(
            content=f"{user.display_name}'s PPE #{result.ppe.id} now has **{result.ppe.points} total points**.",
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )

        if overlay_path and image_path and overlay_path != image_path:
            if os.path.exists(overlay_path):
                os.remove(overlay_path)
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
