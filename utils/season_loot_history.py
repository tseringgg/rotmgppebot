"""Utilities for season loot history."""

from __future__ import annotations

from typing import Any, Dict
from utils.loot_constants import normalize_rarity as normalize_loot_rarity

from utils.item_log_timestamps import (
    now_unix_utc,
    parse_seasonal_item_variant_key,
    seasonal_item_key,
    seasonal_item_variant_key,
)


def normalize_rarity(value: Any, fallback: str = "common") -> str:
    return normalize_loot_rarity(value, fallback)


def _normalize_history_map(raw_history: Any) -> Dict[str, list[int]]:
    result: Dict[str, list[int]] = {}
    if not isinstance(raw_history, dict):
        return result

    for raw_key, raw_values in raw_history.items():
        parsed = parse_seasonal_item_variant_key(raw_key)
        if parsed is None:
            continue

        item_name, shiny, rarity = parsed
        key = seasonal_item_variant_key(item_name, shiny, rarity)

        values = raw_values if isinstance(raw_values, list) else [raw_values]
        timestamps: list[int] = []
        for raw_ts in values:
            try:
                parsed_ts = int(raw_ts)
            except (TypeError, ValueError):
                continue
            if parsed_ts > 0:
                timestamps.append(parsed_ts)

        if timestamps:
            timestamps.sort()
            result[key] = timestamps

    return result
def add_season_item_log(
    player_data: Any,
    *,
    item_name: str,
    shiny: bool,
    rarity: str,
    timestamp: int | None = None,
) -> int:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    logged_at = int(timestamp) if timestamp is not None else now_unix_utc()
    if logged_at <= 0:
        logged_at = now_unix_utc()

    key = seasonal_item_variant_key(item_name, shiny, normalize_rarity(rarity))
    history.setdefault(key, []).append(logged_at)
    history[key].sort()

    player_data.season_item_history = history
    return len(history[key])


def remove_season_item_log(
    player_data: Any,
    *,
    item_name: str,
    shiny: bool,
    rarity: str,
    remove_all: bool = False,
) -> int:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    key = seasonal_item_variant_key(item_name, shiny, normalize_rarity(rarity))
    timestamps = list(history.get(key, []))

    if not timestamps:
        return 0

    removed_count = len(timestamps) if remove_all else 1
    if remove_all:
        history.pop(key, None)
    else:
        timestamps.sort()
        timestamps.pop()
        if timestamps:
            history[key] = timestamps
        else:
            history.pop(key, None)

    player_data.season_item_history = history
    return removed_count


def iter_season_variants(player_data: Any) -> list[tuple[str, bool, str, list[int]]]:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    variants: list[tuple[str, bool, str, list[int]]] = []

    for key, timestamps in history.items():
        parsed = parse_seasonal_item_variant_key(key)
        if parsed is None:
            continue
        item_name, shiny, rarity = parsed
        variants.append((item_name, shiny, rarity, list(timestamps)))

    variants.sort(key=lambda row: (row[0].lower(), row[1], row[2]))
    return variants


def total_season_logs(player_data: Any) -> int:
    return sum(len(ts) for _, _, _, ts in iter_season_variants(player_data))


def unique_season_item_count(player_data: Any) -> int:
    seen = {(item_name, shiny) for item_name, shiny, _rarity, _ts in iter_season_variants(player_data)}
    return len(seen)


def season_unique_items(player_data: Any) -> set[tuple[str, bool]]:
    """Return the set of unique seasonal item/base-shiny pairs for a player."""
    return {(item_name, shiny) for item_name, shiny, _rarity, _ts in iter_season_variants(player_data)}


def season_variant_count(player_data: Any) -> int:
    return len(iter_season_variants(player_data))


def delete_season_item_all_rarities(player_data: Any, *, item_name: str, shiny: bool) -> int:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    target_prefix = seasonal_item_key(item_name, shiny) + "|"
    matching_keys = [key for key in history.keys() if isinstance(key, str) and key.startswith(target_prefix)]
    removed = 0
    for key in matching_keys:
        removed += len(history.get(key, []))
        history.pop(key, None)

    player_data.season_item_history = history
    return removed
