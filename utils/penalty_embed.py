import discord

from utils.points_service import starting_penalty_breakdown_from_inputs


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
    guild_config: dict | None = None,
) -> discord.Embed:
    breakdown = starting_penalty_breakdown_from_inputs(
        pet_level,
        num_exalts,
        percent_loot,
        incombat_reduction,
        guild_config=guild_config,
    )

    def _line(prefix: str, details: dict[str, float], raw_value: float) -> str:
        reduction_points = _format_points(details["reduction_points"])
        final_points = _format_points(details["adjusted_points"])
        reduction_percent = float(details["reduction_percent"])
        if reduction_percent <= 0:
            return f"{prefix} -> {_format_points(abs(raw_value))} points (no reduction, final {final_points})"
        return (
            f"{prefix} -> {_format_points(abs(raw_value))} points "
            f"(-{reduction_points} from {reduction_percent:.2f}% reduction, final {final_points})"
        )

    embed = discord.Embed(
        title="🧾 Starting Points Breakdown",
        description="Here is how starting penalties contribute to total PPE points after any pet reductions.",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="Pet Level Penalty",
        value=_line(f"Level {pet_level}", breakdown["Pet Level Penalty"], pet_penalty),
        inline=True,
    )
    embed.add_field(
        name="Exalts Penalty",
        value=_line(f"{num_exalts} exalts", breakdown["Exalts Penalty"], exalt_penalty),
        inline=True,
    )
    embed.add_field(
        name="Loot Boost Penalty",
        value=_line(f"{percent_loot:g}% boost", breakdown["Loot Boost Penalty"], loot_penalty),
        inline=True,
    )
    embed.add_field(
        name="In-Combat Reduction Penalty",
        value=_line(f"{incombat_reduction:g}s", breakdown["In-Combat Reduction Penalty"], incombat_penalty),
        inline=True,
    )
    embed.add_field(
        name="Total PPE Points",
        value=f"**{_format_points(total_points)} points**",
        inline=False,
    )

    return embed
