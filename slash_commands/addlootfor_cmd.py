import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.calc_points import calc_points, load_loot_points
from utils.player_manager import player_manager
from utils.embed_builders import build_loot_embed
from utils.loot_data import LOOT

async def command(interaction: discord.Interaction, user: discord.Member, id: int, item_name: str, divine: bool = False, shiny: bool = False):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
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
        # Calculate points for the item
        points = calc_points(item_name, divine, shiny)
        
        # Add loot and points using player_manager
        final_key, points_added, updated_ppe, _quest_update = await player_manager.add_loot_and_points(
            interaction, user=user, ppe_id=id, item_name=item_name, divine=divine, shiny=shiny, points=points
        )
        
        # Build embed
        embed = await build_loot_embed(updated_ppe, user_id=user.id, recently_added=item_name)
        
        await interaction.response.send_message(
            f"> ✅ Added **1x {final_key}** to {user.mention}'s PPE #{updated_ppe.id} ({updated_ppe.name})!\n"
            f"**+{points_added} points**\n"
        )
        await interaction.followup.send(
            content=f"{user.display_name}'s PPE #{updated_ppe.id} now has **{updated_ppe.points} total points**.",
            view=embed,
            embed=embed.embeds[0],
            ephemeral=True
        )
        
    except (ValueError, KeyError, LookupError) as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
