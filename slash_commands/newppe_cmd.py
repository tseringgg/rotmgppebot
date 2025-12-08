

import discord

from dataclass import Bonus, PPEData, ROTMGClass
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

    # --- Validate other inputs ---
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

    guild_id = interaction.guild.id
    records = await load_player_records(interaction)
    key = ensure_player_exists(records, interaction.user.id)

    player_data = records[key]

    # --- PPE limit check ---
    ppe_count = len(player_data.ppes)
    if ppe_count >= 10:
        return await interaction.response.send_message(
            "⚠️ You’ve reached the limit of `10 PPEs`. "
            "Delete or reuse an existing one before making a new one."
        )


    # --- Create new PPE ---
    next_id = max((ppe.id for ppe in player_data.ppes), default=0) + 1

    # Calculate each handicap component separately for the receipt
    pet_penalty = -round(pet_level / 4)
    exalt_penalty = -0.5 * num_exalts
    loot_penalty = -2 * percent_loot
    incombat_penalty = -(2 * (incombat_reduction / 0.2))
    
    points = pet_penalty + exalt_penalty + loot_penalty + incombat_penalty

    penalties: list[Bonus] = []
    if pet_penalty != 0:
        penalties.append(Bonus(name="Pet Level Penalty", points=pet_penalty, repeatable=False))
    if exalt_penalty != 0:
        penalties.append(Bonus(name="Exalts Penalty", points=exalt_penalty, repeatable=False))
    if loot_penalty != 0:
        penalties.append(Bonus(name="Loot Boost Penalty", points=loot_penalty, repeatable=False))
    if incombat_penalty != 0:
        penalties.append(Bonus(name="In-Combat Reduction Penalty", points=incombat_penalty, repeatable=False))

    new_ppe = PPEData(
        id=next_id,
        name=class_enum,
        points=points,
        loot=[],
        bonuses=penalties
    )

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
        f"You now have {ppe_count + 1}/10 PPEs.",
        embed=embed
    )