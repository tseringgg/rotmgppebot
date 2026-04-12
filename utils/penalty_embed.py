"""Utilities for penalty embed."""

import discord

from utils.points_service import format_starting_penalty_line, starting_penalty_breakdown_from_inputs


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

    def _line(label: str, value_text: str, details: dict[str, float]) -> str:
        return format_starting_penalty_line(label, value_text, details)

    embed = discord.Embed(
        title="🧾 Starting Points Breakdown",
        description="Here is how starting penalties contribute to total PPE points after any pet reductions.",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="Pet Level Penalty",
        value=_line("Pet Level", str(pet_level), breakdown["Pet Level Penalty"]),
        inline=True,
    )
    embed.add_field(
        name="Exalts Penalty",
        value=_line("Exalts", str(num_exalts), breakdown["Exalts Penalty"]),
        inline=True,
    )
    embed.add_field(
        name="Loot Boost Penalty",
        value=_line("Loot Boost", f"{percent_loot:g}%", breakdown["Loot Boost Penalty"]),
        inline=True,
    )
    embed.add_field(
        name="In-Combat Reduction Penalty",
        value=_line("In-Combat Reduction", f"{incombat_reduction:g}s", breakdown["In-Combat Reduction Penalty"]),
        inline=True,
    )
    embed.add_field(
        name="Total PPE Points",
        value=f"**{_format_points(total_points)} points**",
        inline=False,
    )

    return embed
