"""Helpers for normalizing event rarity payloads."""

from __future__ import annotations

from typing import Any

from utils.loot_constants import normalize_rarity


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_event_rarity(raw_item_rarity: Any, legacy_divine_flag: Any = False) -> str:
    """Resolve event rarity while keeping explicit rarity authoritative.

    Legacy sniffer payloads may still provide a standalone ``divine`` boolean.
    We only use that flag as a fallback when ``item_rarity`` is missing/invalid.
    """
    explicit_rarity = normalize_rarity(raw_item_rarity, fallback="")
    if explicit_rarity:
        return explicit_rarity
    return "divine" if _as_bool(legacy_divine_flag) else "common"
