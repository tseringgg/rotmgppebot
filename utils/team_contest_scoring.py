"""Team contest scoring helpers shared across team-facing menus and commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord

from utils.guild_config import get_contest_settings, get_quest_points


@dataclass(slots=True)
class TeamContestScoring:
    """Resolved scoring inputs for team contest point calculations."""

    include_quest_points: bool
    regular_quest_points: int = 0
    shiny_quest_points: int = 0
    skin_quest_points: int = 0


async def load_team_contest_scoring(interaction: discord.Interaction) -> TeamContestScoring:
    """Load team contest scoring configuration for the current guild."""
    contest_settings = await get_contest_settings(interaction)
    include_quest_points = bool(contest_settings.get("team_contest_include_quest_points", False))
    if not include_quest_points:
        return TeamContestScoring(include_quest_points=False)

    regular_qp, shiny_qp, skin_qp = await get_quest_points(interaction)
    return TeamContestScoring(
        include_quest_points=True,
        regular_quest_points=int(regular_qp),
        shiny_quest_points=int(shiny_qp),
        skin_quest_points=int(skin_qp),
    )


def compute_team_member_points(
    player_data: Any,
    *,
    scoring: TeamContestScoring,
) -> tuple[float, float, float]:
    """Compute PPE points, quest points, and total contribution for one player."""
    ppe_points = 0.0
    if player_data and getattr(player_data, "ppes", None):
        ppe_points = float(max(ppe.points for ppe in player_data.ppes))

    quest_points = 0.0
    if player_data and scoring.include_quest_points:
        quests = getattr(player_data, "quests", None)
        if quests is not None:
            quest_points = float(
                len(getattr(quests, "completed_items", [])) * scoring.regular_quest_points
                + len(getattr(quests, "completed_shinies", [])) * scoring.shiny_quest_points
                + len(getattr(quests, "completed_skins", [])) * scoring.skin_quest_points
            )

    total_points = ppe_points + quest_points
    return ppe_points, quest_points, total_points


def format_points_breakdown(
    *,
    ppe_points: float,
    quest_points: float,
    total_points: float,
    include_quest_points: bool,
    bold_total: bool = True,
) -> str:
    """Format a reusable PPE/quest/total points breakdown string."""
    if include_quest_points:
        total_text = f"**{total_points:.1f}**" if bold_total else f"{total_points:.1f}"
        return f"{ppe_points:.1f} PPE + {quest_points:.1f} Quest = {total_text}"

    total_text = f"**{total_points:.1f}**" if bold_total else f"{total_points:.1f}"
    return f"{ppe_points:.1f} PPE = {total_text}"


def total_points_label(*, include_quest_points: bool) -> str:
    """Return the standard embed field label for team totals."""
    if include_quest_points:
        return "Total: PPE + Quest"
    return "Total: PPE Only"
