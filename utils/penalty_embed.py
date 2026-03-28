import discord


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def build_penalty_infographic_embed(
    *,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    pet_penalty: float,
    exalt_penalty: float,
    loot_penalty: float,
    incombat_penalty: float,
    total_points: float,
) -> discord.Embed:
    embed = discord.Embed(
        title="🧾 Starting Points Breakdown",
        description="Here is how starting penalties contribute to total PPE points.",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="Pet Level Penalty",
        value=f"Level {pet_level} -> {_format_points(pet_penalty)} points",
        inline=True,
    )
    embed.add_field(
        name="Exalts Penalty",
        value=f"{num_exalts} exalts -> {_format_points(exalt_penalty)} points",
        inline=True,
    )
    embed.add_field(
        name="Loot Boost Penalty",
        value=f"{percent_loot:g}% boost -> {_format_points(loot_penalty)} points",
        inline=True,
    )
    embed.add_field(
        name="In-Combat Reduction Penalty",
        value=f"{incombat_reduction:g}s -> {_format_points(incombat_penalty)} points",
        inline=True,
    )
    embed.add_field(
        name="Total PPE Points",
        value=f"**{_format_points(total_points)} points**",
        inline=False,
    )

    return embed
