"""Utilities for item log timestamps."""

from __future__ import annotations

from datetime import datetime, timezone

from utils.calc_points import normalize_item_name


def now_unix_utc() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def seasonal_item_key(item_name: str, shiny: bool) -> str:
    normalized = normalize_item_name(item_name)
    return f"{normalized}|{1 if shiny else 0}"


def seasonal_item_variant_key(item_name: str, shiny: bool, rarity: str) -> str:
    normalized = normalize_item_name(item_name)
    normalized_rarity = str(rarity or "common").strip().lower() or "common"
    return f"{normalized}|{1 if shiny else 0}|{normalized_rarity}"


def parse_seasonal_item_variant_key(key: str) -> tuple[str, bool, str] | None:
    if not isinstance(key, str):
        return None
    parts = key.split("|")
    if len(parts) != 3:
        return None

    item_name = normalize_item_name(parts[0])
    if not item_name:
        return None

    shiny_part = parts[1].strip()
    if shiny_part not in {"0", "1"}:
        return None

    rarity = parts[2].strip().lower() or "common"
    return item_name, shiny_part == "1", rarity


def format_unix_utc(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    try:
        parsed = int(timestamp)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return datetime.fromtimestamp(parsed, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
