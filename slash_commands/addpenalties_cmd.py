import discord
from dataclass import Bonus
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import build_loot_embed

async def command(interaction: discord.Interaction, user: discord.Member, id: int, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
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
    if not hasattr(target_ppe, 'bonuses') or target_ppe.bonuses is None:
        target_ppe.bonuses = []

    # Remove existing penalties with the same names and subtract their points
    removed_penalties = []
    for penalty_name in penalty_names:
        for i in range(len(target_ppe.bonuses) - 1, -1, -1):  # Iterate backwards to safely remove items
            bonus = target_ppe.bonuses[i]
            if bonus.name == penalty_name:
                removed_penalty = target_ppe.bonuses.pop(i)
                target_ppe.points -= removed_penalty.points
                removed_penalties.append(removed_penalty)
                break

    # Add new penalties and update points
    total_penalty_points = 0
    for penalty in new_penalties:
        target_ppe.bonuses.append(penalty)
        target_ppe.points += penalty.points
        total_penalty_points += penalty.points

    # Save records
    await save_player_records(interaction=interaction, records=records)

    # Create response message and embed
    embed = await build_loot_embed(target_ppe)
    
    removed_text = ""
    if removed_penalties:
        removed_names = [p.name for p in removed_penalties]
        removed_text = f"\nReplaced existing penalties: {', '.join(removed_names)}"

    await interaction.response.send_message(
        f"✅ Added penalties to {user.display_name}'s PPE #{target_ppe.id} ({target_ppe.name})!\n"
        f"**{total_penalty_points} penalty points** applied{removed_text}\n"
        f"Their PPE now has **{target_ppe.points} total points**.",
        embed=embed
    )