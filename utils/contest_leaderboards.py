"""Shared contest leaderboard identifiers and formatting helpers."""

from __future__ import annotations

from typing import Final


CONTEST_LEADERBOARD_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("ppe", "PPE Leaderboard"),
    ("quest", "Quest Leaderboard"),
    ("season", "Season Loot Leaderboard"),
    ("team", "Team Leaderboard"),
    ("character", "Character Leaderboard"),
    ("additional_team", "Additional Team Leaderboards"),
)

CONTEST_LEADERBOARD_LABELS: Final[dict[str, str]] = dict(CONTEST_LEADERBOARD_OPTIONS)
VALID_CONTEST_LEADERBOARD_IDS: Final[frozenset[str]] = frozenset(CONTEST_LEADERBOARD_LABELS.keys())

_CONTEST_LEADERBOARD_ALIASES: Final[dict[str, str]] = {
    "additional_team_leaderboard": "additional_team",
    "additional_team_leaderboards": "additional_team",
    "additional team": "additional_team",
    "additional team leaderboard": "additional_team",
    "additional team leaderboards": "additional_team",
}


def normalize_contest_leaderboard_id(raw_value: object) -> str | None:
    """Normalize and validate a contest leaderboard identifier."""
    if not isinstance(raw_value, str):
        return None

    normalized = raw_value.strip().lower()
    if normalized in VALID_CONTEST_LEADERBOARD_IDS:
        return normalized
    return _CONTEST_LEADERBOARD_ALIASES.get(normalized)


def contest_leaderboard_label(raw_value: object, *, fallback: str = "Not Set") -> str:
    """Return a display label for a contest leaderboard identifier."""
    normalized = normalize_contest_leaderboard_id(raw_value)
    if normalized is None:
        return fallback
    return CONTEST_LEADERBOARD_LABELS[normalized]
