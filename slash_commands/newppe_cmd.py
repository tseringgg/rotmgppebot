

import discord

from dataclass import PPEData, ROTMGClass
from utils.guild_config import get_max_ppes, load_guild_config
from utils.points_service import apply_penalties_to_ppe, recompute_ppe_points, validate_penalty_inputs
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


async def command(interaction: discord.Interaction, class_name: str, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")
    # --- Validate class name ---
    class_enum = next((c for c in ROTMGClass if c.value == class_name), None)
    if not class_enum:
        return await interaction.response.send_message(
            f"❌ `{class_name}` is not a valid RotMG class.\n"
            f"Use the autocomplete list to choose one.",
            ephemeral=True
        )

    error = validate_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

    guild_id = interaction.guild.id
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)

    player_data = records[key]

    max_ppes = await get_max_ppes(interaction)

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= max_ppes:
        return await interaction.response.send_message(
            f"⚠️ You’ve reached the limit of `{max_ppes} PPEs`. "
            "Delete or reuse an existing one before making a new one."
        )


    # --- Create new PPE ---
    next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1

    new_ppe = PPEData(
        id=next_id,
        name=class_enum,
        points=0.0,
        loot=[],
        bonuses=[]
    )

    penalty_result = apply_penalties_to_ppe(
        new_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
    )
    components = penalty_result["components"]
    pet_penalty = components["Pet Level Penalty"]
    exalt_penalty = components["Exalts Penalty"]
    loot_penalty = components["Loot Boost Penalty"]
    incombat_penalty = components["In-Combat Reduction Penalty"]

    guild_config = await load_guild_config(interaction)
    points_breakdown = recompute_ppe_points(new_ppe, guild_config)
    points = points_breakdown["total"]

    player_data.ppes.append(new_ppe)
    player_data.active_ppe = next_id

    await save_player_records(interaction=interaction, records=records)

    # Create embed for handicap breakdown
    embed = discord.Embed(
        title="🧾 Starting Points Breakdown",
        description="Here's how your starting points were calculated:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Pet Level Penalty",
        value=f"Level {pet_level} → {pet_penalty} points",
        inline=True
    )
    
    embed.add_field(
        name="Exalts Penalty", 
        value=f"{num_exalts} exalts → {exalt_penalty} points",
        inline=True
    )
    
    embed.add_field(
        name="Loot Boost Penalty",
        value=f"{percent_loot}% boost → {loot_penalty} points", 
        inline=True
    )
    
    embed.add_field(
        name="In-Combat Reduction Penalty",
        value=f"{incombat_reduction} reduction → {incombat_penalty} points",
        inline=True
    )
    
    embed.add_field(
        name="**Total Starting Points**",
        value=f"**{points} points**",
        inline=False
    )

    await interaction.response.send_message(
        f"✅ Created `PPE #{next_id}` for your `{class_enum.value}` "
        f"and set it as your active PPE.\n"
        f"You now have {ppe_count + 1}/{max_ppes} PPEs.",
        embed=embed
    )