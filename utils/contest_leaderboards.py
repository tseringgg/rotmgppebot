"""Shared contest leaderboard identifiers and formatting helpers."""

from __future__ import annotations

from typing import Final


CONTEST_LEADERBOARD_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("ppe", "PPE Leaderboard"),
    ("quest", "Quest Leaderboard"),
    ("season", "Season Loot Leaderboard"),
    ("team", "Team Leaderboard"),
)

CONTEST_LEADERBOARD_LABELS: Final[dict[str, str]] = dict(CONTEST_LEADERBOARD_OPTIONS)
VALID_CONTEST_LEADERBOARD_IDS: Final[frozenset[str]] = frozenset(CONTEST_LEADERBOARD_LABELS.keys())


def normalize_contest_leaderboard_id(raw_value: object) -> str | None:
    """Normalize and validate a contest leaderboard identifier."""
    if not isinstance(raw_value, str):
        return None

    normalized = raw_value.strip().lower()
    if normalized in VALID_CONTEST_LEADERBOARD_IDS:
        return normalized
    return None


def contest_leaderboard_label(raw_value: object, *, fallback: str = "Not Set") -> str:
    """Return a display label for a contest leaderboard identifier."""
    normalized = normalize_contest_leaderboard_id(raw_value)
    if normalized is None:
        return fallback
    return CONTEST_LEADERBOARD_LABELS[normalized]
