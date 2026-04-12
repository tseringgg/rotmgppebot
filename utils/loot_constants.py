"""Utilities for loot constants."""

from __future__ import annotations

from typing import Any

RARITY_CHOICES: tuple[str, ...] = ("common", "uncommon", "rare", "legendary", "divine")


def normalize_rarity(value: Any, fallback: str = "common") -> str:
    raw = str(value).strip().lower() if value is not None else ""
    if raw in RARITY_CHOICES:
        return raw
    return fallback


def rarity_rank(value: Any) -> int:
    rarity = normalize_rarity(value)
    try:
        return RARITY_CHOICES.index(rarity)
    except ValueError:
        return 0
