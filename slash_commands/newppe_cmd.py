

import discord

from dataclass import PPEData, ROTMGClass
from utils.penalty_embed import build_penalty_infographic_embed
from utils.guild_config import get_max_ppes, load_guild_config
from utils.points_service import apply_penalties_to_ppe, parse_penalty_inputs, recompute_ppe_points
from utils.player_records import ensure_player_exists, load_player_records, save_player_records


async def create_new_ppe_for_user(
    interaction: discord.Interaction,
    *,
    class_name: str,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    target_user_id: int | None = None,
) -> dict:
    """Create a new PPE for a user.

    Args:
        interaction: The discord interaction.
        class_name: The ROTMG class name.
        pet_level: Pet level (0-100).
        num_exalts: Number of exalts (0-40).
        percent_loot: Loot boost percentage (0-25).
        incombat_reduction: In-combat reduction value.
        target_user_id: Optional. The user ID to create the PPE for. Defaults to interaction.user.id.
    """
    if not interaction.guild:
        raise ValueError("❌ This command can only be used in a server.")

    # --- Validate class name ---
    class_enum = next((c for c in ROTMGClass if c.value == class_name), None)
    if not class_enum:
        raise ValueError(
            f"❌ `{class_name}` is not a valid RotMG class.\n"
            f"Use the autocomplete list to choose one.",
        )

    parsed_inputs, error = parse_penalty_inputs(pet_level, num_exalts, percent_loot, incombat_reduction)
    if error:
        raise ValueError(error)

    assert parsed_inputs is not None
    pet_level = int(parsed_inputs["pet_level"])
    num_exalts = int(parsed_inputs["num_exalts"])
    percent_loot = float(parsed_inputs["percent_loot"])
    incombat_reduction = float(parsed_inputs["incombat_reduction"])

    guild_id = interaction.guild.id
    records = await load_player_records(interaction)
    user_id = target_user_id if target_user_id is not None else interaction.user.id
    key = ensure_player_exists(records, user_id)

    player_data = records[key]

    max_ppes = await get_max_ppes(interaction)

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= max_ppes:
        raise ValueError(
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

    guild_config = await load_guild_config(interaction)

    penalty_result = apply_penalties_to_ppe(
        new_ppe,
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        guild_config=guild_config,
    )
    components = penalty_result["components"]
    pet_penalty = components["Pet Level Penalty"]
    exalt_penalty = components["Exalts Penalty"]
    loot_penalty = components["Loot Boost Penalty"]
    incombat_penalty = components["In-Combat Reduction Penalty"]

    points_breakdown = recompute_ppe_points(new_ppe, guild_config)
    points = points_breakdown["total"]

    player_data.ppes.append(new_ppe)
    player_data.active_ppe = next_id

    await save_player_records(interaction=interaction, records=records)

    embed = build_penalty_infographic_embed(
        pet_level=pet_level,
        num_exalts=num_exalts,
        percent_loot=percent_loot,
        incombat_reduction=incombat_reduction,
        pet_penalty=pet_penalty,
        exalt_penalty=exalt_penalty,
        loot_penalty=loot_penalty,
        incombat_penalty=incombat_penalty,
        total_points=points,
    )

    return {
        "next_id": next_id,
        "class_name": class_enum.value,
        "ppe_count": ppe_count + 1,
        "max_ppes": max_ppes,
        "embed": embed,
    }


async def command(interaction: discord.Interaction, class_name: str, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float):
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.")

    try:
        result = await create_new_ppe_for_user(
            interaction,
            class_name=class_name,
            pet_level=pet_level,
            num_exalts=num_exalts,
            percent_loot=percent_loot,
            incombat_reduction=incombat_reduction,
        )
    except ValueError as exc:
        return await interaction.response.send_message(str(exc), ephemeral=True)

    await interaction.response.send_message(
        f"✅ Created `PPE #{result['next_id']}` for your `{result['class_name']}` "
        f"and set it as your active PPE.\n"
        f"You now have {result['ppe_count']}/{result['max_ppes']} PPEs.",
        embed=result["embed"],
    )