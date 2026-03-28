import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.embed_builders import build_loot_embed
from utils.guild_config import load_guild_config
from utils.points_service import apply_penalties_to_ppe, recompute_ppe_points, validate_penalty_inputs

async def command(interaction: discord.Interaction, user: discord.Member, id: int, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    error = validate_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

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

    penalty_result = apply_penalties_to_ppe(
        target_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
    )
    guild_config = await load_guild_config(interaction)
    recompute_ppe_points(target_ppe, guild_config)

    # Save records
    await save_player_records(interaction=interaction, records=records)

    # Create response message
    penalty_list = []
    for penalty in penalty_result["new_penalties"]:
        penalty_list.append(f"• {penalty.name}: {penalty.points} pts")
    
    penalty_text = "\n".join(penalty_list) if penalty_list else "No penalties applied (all values were 0)"
    
    removed_points = penalty_result["removed_penalty_points"]
    total_penalty_points = penalty_result["new_penalty_points"]
    removed_text = f"\nRemoved previous penalties: {removed_points} pts" if removed_points != 0 else ""
    
    # Create embed
    embed = await build_loot_embed(target_ppe, user_id=user.id)
    
    await interaction.response.send_message(
        f"✅ Applied penalties to {user.mention}'s PPE #{target_ppe.id} ({target_ppe.name})!\n\n"
        f"**Penalties Applied:**\n{penalty_text}\n"
        f"**Total penalty:** {total_penalty_points} points{removed_text}\n"
    )
    await interaction.followup.send(
        f"Their PPE now has **{target_ppe.points} total points**.",
        view=embed,
        embed=embed.embeds[0],
        ephemeral=True
    )