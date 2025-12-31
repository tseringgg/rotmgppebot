import discord
from dataclass import Bonus
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.bonus_data import load_bonuses
from utils.embed_builders import build_loot_embed

async def command(interaction: discord.Interaction, user: discord.Member, id: int, bonus_name: str):
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
    
    bonus_data = available_bonuses[bonus_name]
    
    # Check if bonus already exists
    existing_bonus = None
    for bonus in target_ppe.bonuses:
        if bonus.name == bonus_name:
            existing_bonus = bonus
            break
    
    if existing_bonus:
        if not bonus_data.repeatable:
            return await interaction.response.send_message(
                f"❌ PPE #{id} already has the `{bonus_name}` bonus. This bonus is not repeatable.",
                ephemeral=True
            )
        # Increment quantity for repeatable bonus
        existing_bonus.quantity += 1
        target_ppe.points += bonus_data.points
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
        target_ppe.bonuses.append(new_bonus)
        target_ppe.points += bonus_data.points
        quantity_text = ""
    
    # Save records
    await save_player_records(interaction=interaction, records=records)
    
    # Create response message and embed
    repeatable_text = " (repeatable)" if bonus_data.repeatable else " (one-time)"
    embed = await build_loot_embed(target_ppe, user_id=user.id, recently_added=bonus_name)
    
    await interaction.response.send_message(
        f"✅ Added bonus `{bonus_name}` to {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})!{quantity_text}\n"
        f"**+{bonus_data.points} points**{repeatable_text}\n"
    )
    await interaction.followup.send(
        f"Your PPE now has **{target_ppe.points} total points**.",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )