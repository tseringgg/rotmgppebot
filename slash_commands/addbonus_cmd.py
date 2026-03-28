import discord
from dataclass import Bonus
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.bonus_data import load_bonuses
from utils.embed_builders import build_loot_embed
from utils.guild_config import load_guild_config
from utils.points_service import recompute_ppe_points

async def command(interaction: discord.Interaction, bonus_name: str):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    
    # Load available bonuses
    available_bonuses = load_bonuses()
    
    # Validate bonus name
    if bonus_name not in available_bonuses:
        return await interaction.response.send_message(
            f"❌ `{bonus_name}` is not a valid bonus.\n"
            f"Use the autocomplete list to choose one.",
            ephemeral=True
        )
    
    # Load player records
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)
    player_data = records[key]
    
    # Check if player has an active PPE
    if player_data.active_ppe is None:
        return await interaction.response.send_message(
            "❌ You don't have an active PPE. Create one first with `/newppe`.",
            ephemeral=True
        )
    
    # Find the active PPE
    active_ppe = None
    for ppe in player_data.ppes:
        if ppe.id == player_data.active_ppe:
            active_ppe = ppe
            break
    
    if not active_ppe:
        return await interaction.response.send_message(
            "❌ Could not find your active PPE.",
            ephemeral=True
        )
    
    bonus_data = available_bonuses[bonus_name]
    
    # Check if bonus already exists
    existing_bonus = None
    for bonus in active_ppe.bonuses:
        if bonus.name == bonus_name:
            existing_bonus = bonus
            break
    
    if existing_bonus:
        if not bonus_data.repeatable:
            return await interaction.response.send_message(
                f"❌ You already have the `{bonus_name}` bonus and it is not repeatable.",
                ephemeral=True
            )
        # Increment quantity for repeatable bonus
        existing_bonus.quantity += 1
        quantity_text = f" (quantity: {existing_bonus.quantity})"
    else:
        # Create new bonus instance
        new_bonus = Bonus(
            name=bonus_data.name,
            points=bonus_data.points,
            repeatable=bonus_data.repeatable,
            quantity=1
        )
        # Add bonus to PPE
        active_ppe.bonuses.append(new_bonus)
        quantity_text = ""

    guild_config = await load_guild_config(interaction)
    recompute_ppe_points(active_ppe, guild_config)
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Create response message and embed
    repeatable_text = " (repeatable)" if bonus_data.repeatable else " (one-time)"
    embed = await build_loot_embed(active_ppe, user_id=interaction.user.id, recently_added=bonus_name)
    
    await interaction.response.send_message(
        f"✅ Added bonus `{bonus_name}` to PPE #{active_ppe.id} ({active_ppe.name})!{quantity_text}\n"
        f"**+{bonus_data.points} points**{repeatable_text}\n"
    )
    await interaction.followup.send(
        f"Your PPE now has **{active_ppe.points} total points**.",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )