import discord
from dataclass import Bonus
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import build_loot_embed

async def command(interaction: discord.Interaction, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    # --- Validate inputs ---
    if not (0 <= pet_level <= 100):
        return await interaction.response.send_message(
            "❌ Pet level must be between `0` and `100`.",
            ephemeral=True
        )
    if not (0 <= num_exalts <= 40):
        return await interaction.response.send_message(
            "❌ Number of exalts must be between `0` and `40`.",
            ephemeral=True
        )
    if not (0.0 <= percent_loot <= 25.0):
        return await interaction.response.send_message(
            "❌ Percent loot boost must be between `0%` and `25%`.",
            ephemeral=True
        )
    if incombat_reduction not in {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}:
        return await interaction.response.send_message(
            "❌ In-combat damage reduction must be one of the following values: `0`, `0.2`, `0.4`, `0.6`, `0.8`, `1`.",
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

    # Calculate penalty components (same logic as newppe_cmd)
    pet_penalty = -round(pet_level / 4)
    exalt_penalty = -0.5 * num_exalts
    loot_penalty = -2 * percent_loot
    incombat_penalty = -(2 * (incombat_reduction / 0.2))

    # Create penalty bonuses
    penalty_names = [
        "Pet Level Penalty",
        "Exalts Penalty", 
        "Loot Boost Penalty",
        "In-Combat Reduction Penalty"
    ]
    
    new_penalties = []
    if pet_penalty != 0:
        new_penalties.append(Bonus(name="Pet Level Penalty", points=pet_penalty, repeatable=False, quantity=1))
    if exalt_penalty != 0:
        new_penalties.append(Bonus(name="Exalts Penalty", points=exalt_penalty, repeatable=False, quantity=1))
    if loot_penalty != 0:
        new_penalties.append(Bonus(name="Loot Boost Penalty", points=loot_penalty, repeatable=False, quantity=1))
    if incombat_penalty != 0:
        new_penalties.append(Bonus(name="In-Combat Reduction Penalty", points=incombat_penalty, repeatable=False, quantity=1))

    # Handle old format PPEs (initialize bonuses list if it doesn't exist)
    if not hasattr(active_ppe, 'bonuses') or active_ppe.bonuses is None:
        active_ppe.bonuses = []

    # Remove existing penalties with the same names and subtract their points
    removed_penalty_points = 0
    bonuses_to_keep = []
    
    for bonus in active_ppe.bonuses:
        if bonus.name in penalty_names:
            removed_penalty_points += bonus.points
        else:
            bonuses_to_keep.append(bonus)
    
    # Replace bonuses list with only non-penalty bonuses
    active_ppe.bonuses = bonuses_to_keep
    
    # Subtract removed penalty points
    active_ppe.points -= removed_penalty_points

    # Add new penalties and their points
    total_penalty_points = 0
    for penalty in new_penalties:
        active_ppe.bonuses.append(penalty)
        total_penalty_points += penalty.points
    
    # Add new penalty points
    active_ppe.points += total_penalty_points

    # Save records
    await save_player_records(interaction=interaction, records=records)

    # Create response message and embed
    embed = await build_loot_embed(active_ppe)
    
    penalty_list = []
    for penalty in new_penalties:
        penalty_list.append(f"• {penalty.name}: {penalty.points} pts")
    
    penalty_text = "\n".join(penalty_list) if penalty_list else "No penalties applied (all values were 0)"
    
    removed_text = f"\nRemoved previous penalties: {removed_penalty_points} pts" if removed_penalty_points != 0 else ""

    await interaction.response.send_message(
        f"✅ Applied penalties to your active PPE #{active_ppe.id} ({active_ppe.name})!\n\n"
        f"**Penalties Applied:**\n{penalty_text}\n"
        f"**Total penalty:** {total_penalty_points} points{removed_text}\n"
    )
    await interaction.followup.send(
        f"Your PPE now has **{active_ppe.points} total points**.",
        embed=embed,
        ephemeral=True
    )