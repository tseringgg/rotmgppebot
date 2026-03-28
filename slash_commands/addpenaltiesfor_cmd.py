import discord
from utils.player_records import ensure_player_exists, load_player_records, save_player_records
from utils.guild_config import load_guild_config
from utils.penalty_embed import build_penalty_infographic_embed
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points

async def command(interaction: discord.Interaction, user: discord.Member, id: int, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    parsed_inputs, error = parse_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

    assert parsed_inputs is not None
    pet_level = int(parsed_inputs["pet_level"])
    num_exalts = int(parsed_inputs["num_exalts"])
    percent_loot = float(parsed_inputs["percent_loot"])
    incombat_reduction = float(parsed_inputs["incombat_reduction"])

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

    guild_config = await load_guild_config(interaction)
    penalty_result = apply_penalties_to_ppe(
        target_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        guild_config=guild_config,
    )
    points_breakdown = recompute_ppe_points(target_ppe, guild_config)

    # Save records
    await save_player_records(interaction=interaction, records=records)

    components = penalty_result["components"]
    embed = build_penalty_infographic_embed(
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        pet_penalty=components["Pet Level Penalty"],
        exalt_penalty=components["Exalts Penalty"],
        loot_penalty=components["Loot Boost Penalty"],
        incombat_penalty=components["In-Combat Reduction Penalty"],
        total_points=points_breakdown["total"],
    )

    removed_points = penalty_result["removed_penalty_points"]
    await interaction.response.send_message(
        f"✅ Applied penalties to {user.mention}'s PPE #{target_ppe.id} ({target_ppe.name}). "
        f"Removed previous penalty points: {removed_points}.",
        embed=embed,
    )