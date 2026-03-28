import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import build_loot_embed
from utils.guild_config import load_guild_config
from utils.points_service import apply_penalties_to_ppe, recompute_ppe_points, validate_penalty_inputs

async def command(interaction: discord.Interaction, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    error = validate_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

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

    if not hasattr(active_ppe, 'bonuses') or active_ppe.bonuses is None:
        active_ppe.bonuses = []

    penalty_result = apply_penalties_to_ppe(
        active_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
    )
    guild_config = await load_guild_config(interaction)
    recompute_ppe_points(active_ppe, guild_config)

    # Save records
    await save_player_records(interaction=interaction, records=records)

    # Create response message and embed
    embed = await build_loot_embed(active_ppe, user_id=interaction.user.id)
    
    penalty_list = []
    for penalty in penalty_result["new_penalties"]:
        penalty_list.append(f"• {penalty.name}: {penalty.points} pts")
    
    penalty_text = "\n".join(penalty_list) if penalty_list else "No penalties applied (all values were 0)"
    
    removed_points = penalty_result["removed_penalty_points"]
    total_penalty_points = penalty_result["new_penalty_points"]
    removed_text = f"\nRemoved previous penalties: {removed_points} pts" if removed_points != 0 else ""

    await interaction.response.send_message(
        f"✅ Applied penalties to your active PPE #{active_ppe.id} ({active_ppe.name})!\n\n"
        f"**Penalties Applied:**\n{penalty_text}\n"
        f"**Total penalty:** {total_penalty_points} points{removed_text}\n"
    )
    await interaction.followup.send(
        f"Your PPE now has **{active_ppe.points} total points**.",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )