"""Team contest scoring helpers shared across team-facing menus and commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord

from utils.calc_points import normalize_item_name
from utils.guild_config import get_contest_settings, get_quest_points
from utils.quest_modes import normalize_team_key


@dataclass(slots=True)
class TeamContestScoring:
    """Resolved scoring inputs for team contest point calculations."""

    include_quest_points: bool
    ppe_aggregate_points: bool = False
    team_aggregate_points: bool = False
    regular_quest_points: int = 0
    shiny_quest_points: int = 0
    skin_quest_points: int = 0


async def load_team_contest_scoring(interaction: discord.Interaction) -> TeamContestScoring:
    """Load team contest scoring configuration for the current guild."""
    contest_settings = await get_contest_settings(interaction)
    include_quest_points = bool(contest_settings.get("team_contest_include_quest_points", False))
    ppe_aggregate_points = bool(contest_settings.get("ppe_aggregate_points_enabled", False))
    team_aggregate_points = bool(contest_settings.get("team_aggregate_points_enabled", False))
    if not include_quest_points:
        return TeamContestScoring(
            include_quest_points=False,
            ppe_aggregate_points=ppe_aggregate_points,
            team_aggregate_points=team_aggregate_points,
        )

    regular_qp, shiny_qp, skin_qp = await get_quest_points(interaction)
    return TeamContestScoring(
        include_quest_points=True,
        ppe_aggregate_points=ppe_aggregate_points,
        team_aggregate_points=team_aggregate_points,
        regular_quest_points=int(regular_qp),
        shiny_quest_points=int(shiny_qp),
        skin_quest_points=int(skin_qp),
    )


def _player_ppes(player_data: Any) -> list[Any]:
    ppes = getattr(player_data, "ppes", None)
    return ppes if isinstance(ppes, list) else []


def _ppe_points_value(ppe: Any) -> float:
    try:
        return float(getattr(ppe, "points", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def get_best_ppe(player_data: Any) -> Any | None:
    """Return the highest-scoring PPE for a player, if any."""
    ppes = _player_ppes(player_data)
    if not ppes:
        return None
    return max(ppes, key=_ppe_points_value)


def compute_ppe_points(player_data: Any, *, aggregate: bool = False) -> float:
    """Compute a player's PPE points, optionally aggregating every character."""
    ppes = _player_ppes(player_data)
    if not ppes:
        return 0.0

    if aggregate:
        total_points = 0.0
        for ppe in ppes:
            total_points += _ppe_points_value(ppe)
        return total_points

    best_ppe = get_best_ppe(player_data)
    if best_ppe is None:
        return 0.0
    return _ppe_points_value(best_ppe)


def compute_team_member_points(
    player_data: Any,
    *,
    scoring: TeamContestScoring,
    aggregate: bool = False,
) -> tuple[float, float, float]:
    """Compute PPE points, quest points, and total contribution for one player."""
    ppe_points = compute_ppe_points(player_data, aggregate=aggregate)

    quest_points = 0.0
    if player_data and scoring.include_quest_points:
        quest_points = compute_quest_points_from_quests(getattr(player_data, "quests", None), scoring=scoring)

    total_points = ppe_points + quest_points
    return ppe_points, quest_points, total_points


def compute_quest_points_from_quests(quests: Any, *, scoring: TeamContestScoring) -> float:
    if quests is None:
        return 0.0
    return float(
        len(getattr(quests, "completed_items", [])) * scoring.regular_quest_points
        + len(getattr(quests, "completed_shinies", [])) * scoring.shiny_quest_points
        + len(getattr(quests, "completed_skins", [])) * scoring.skin_quest_points
    )


def compute_quest_points_from_state(state: dict[str, Any] | None, *, scoring: TeamContestScoring) -> float:
    if not isinstance(state, dict):
        return 0.0
    return float(
        len(state.get("completed_items", [])) * scoring.regular_quest_points
        + len(state.get("completed_shinies", [])) * scoring.shiny_quest_points
        + len(state.get("completed_skins", [])) * scoring.skin_quest_points
    )


def _strip_shiny_suffix(item_name: str) -> str:
    normalized = normalize_item_name(item_name)
    if normalized.lower().endswith("(shiny)"):
        return normalized[: -len("(shiny)")].strip()
    return normalized


def _normalized_variant_key(item_name: str, *, shiny: bool) -> tuple[str, bool]:
    return (_strip_shiny_suffix(item_name).lower(), bool(shiny))


def _active_ppe_loot_variant_keys(active_ppe: Any) -> set[tuple[str, bool]]:
    if active_ppe is None:
        return set()

    loot_entries = getattr(active_ppe, "loot", None)
    if not isinstance(loot_entries, list):
        return set()

    keys: set[tuple[str, bool]] = set()
    for loot in loot_entries:
        try:
            quantity = int(getattr(loot, "quantity", 0) or 0)
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            continue

        item_name = str(getattr(loot, "item_name", "") or "").strip()
        if not item_name:
            continue
        keys.add(_normalized_variant_key(item_name, shiny=bool(getattr(loot, "shiny", False))))
    return keys


def compute_active_ppe_completed_quest_counts(quests: Any, active_ppe: Any) -> dict[str, int]:
    """Count completed quests that overlap with loot on the active PPE."""
    if quests is None:
        return {
            "regular": 0,
            "shiny": 0,
            "skin": 0,
            "total": 0,
        }

    active_loot = _active_ppe_loot_variant_keys(active_ppe)
    if not active_loot:
        return {
            "regular": 0,
            "shiny": 0,
            "skin": 0,
            "total": 0,
        }

    regular = sum(
        1
        for item_name in getattr(quests, "completed_items", [])
        if _normalized_variant_key(str(item_name), shiny=False) in active_loot
    )
    shiny = sum(
        1
        for item_name in getattr(quests, "completed_shinies", [])
        if _normalized_variant_key(str(item_name), shiny=True) in active_loot
    )
    skin = sum(
        1
        for item_name in getattr(quests, "completed_skins", [])
        if _normalized_variant_key(str(item_name), shiny=False) in active_loot
    )
    return {
        "regular": regular,
        "shiny": shiny,
        "skin": skin,
        "total": regular + shiny + skin,
    }


def compute_quest_points_from_quests_and_active_ppe(
    quests: Any,
    active_ppe: Any,
    *,
    scoring: TeamContestScoring,
) -> float:
    counts = compute_active_ppe_completed_quest_counts(quests, active_ppe)
    return float(
        counts["regular"] * scoring.regular_quest_points
        + counts["shiny"] * scoring.shiny_quest_points
        + counts["skin"] * scoring.skin_quest_points
    )


def compute_team_shared_quest_points(
    *,
    team_name: str,
    quest_settings: dict[str, Any],
    scoring: TeamContestScoring,
) -> float:
    if not bool(quest_settings.get("enable_team_quests", False)):
        return 0.0
    if bool(quest_settings.get("use_global_quests", False)):
        return 0.0

    state_map = quest_settings.get("team_quests_state", {})
    if not isinstance(state_map, dict):
        return 0.0

    key = normalize_team_key(team_name)
    state = state_map.get(key)
    return compute_quest_points_from_state(state, scoring=scoring)


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
