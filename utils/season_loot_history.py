"""Utilities for season loot history."""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from utils.loot_constants import normalize_rarity as normalize_loot_rarity

from utils.item_log_timestamps import (
    now_unix_utc,
    parse_seasonal_item_variant_key,
    seasonal_item_key,
    seasonal_item_variant_key,
)

_LOOT_CSV_PATH = Path("rotmg_loot_drops_updated.csv")
_APOSTROPHE_VARIANTS = "\u2018\u2019\u02bc\u2032\u00b4`"
_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def normalize_rarity(value: Any, fallback: str = "common") -> str:
    return normalize_loot_rarity(value, fallback)


def _normalize_item_name(name: str) -> str:
    if not name:
        return ""
    normalized = name
    for apostrophe in _APOSTROPHE_VARIANTS:
        normalized = normalized.replace(apostrophe, "'")
    for dash in _DASH_VARIANTS:
        normalized = normalized.replace(dash, "-")
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    normalized = " ".join(normalized.split())
    return normalized.strip()


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


def collect_season_variants(player_data_iterable: Any) -> list[tuple[str, bool, str, list[int]]]:
    variants: list[tuple[str, bool, str, list[int]]] = []
    if player_data_iterable is None:
        return variants

    for player_data in player_data_iterable:
        variants.extend(iter_season_variants(player_data))

    variants.sort(key=lambda row: (row[0].lower(), row[1], row[2]))
    return variants


def _is_limited_variant(rarity: str) -> bool:
    return str(rarity).strip().lower() == "limited"


@lru_cache(maxsize=1)
def _load_casefolded_loot_types() -> dict[str, str]:
    lookup: dict[str, str] = {}
    with _LOOT_CSV_PATH.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            item_name = _normalize_item_name(str(row.get("Item Name", "")).strip()).casefold()
            loot_type = str(row.get("Loot Type", "")).strip().lower()
            if item_name:
                lookup[item_name] = loot_type
    return lookup


def _is_limited_item(item_name: str, shiny: bool, rarity: str) -> bool:
    if _is_limited_variant(rarity):
        return True

    try:
        loot_types = _load_casefolded_loot_types()
    except OSError:
        return False

    normalized_name = _normalize_item_name(item_name).casefold()
    if shiny and loot_types.get(f"{normalized_name} (shiny)") == "limited":
        return True
    return loot_types.get(normalized_name) == "limited"


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


def iter_season_variants(player_data: Any, *, exclude_limited: bool = False) -> list[tuple[str, bool, str, list[int]]]:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    variants: list[tuple[str, bool, str, list[int]]] = []

    for key, timestamps in history.items():
        parsed = parse_seasonal_item_variant_key(key)
        if parsed is None:
            continue
        item_name, shiny, rarity = parsed
        if exclude_limited and _is_limited_item(item_name, shiny, rarity):
            continue
        variants.append((item_name, shiny, rarity, list(timestamps)))

    variants.sort(key=lambda row: (row[0].lower(), row[1], row[2]))
    return variants


def total_season_logs(player_data: Any) -> int:
    return sum(len(ts) for _, _, _, ts in iter_season_variants(player_data))


def unique_season_item_count(player_data: Any, *, exclude_limited: bool = False) -> int:
    seen = {
        (item_name, shiny)
        for item_name, shiny, _rarity, _ts in iter_season_variants(player_data, exclude_limited=exclude_limited)
    }
    return len(seen)


def season_unique_items(player_data: Any, *, exclude_limited: bool = False) -> set[tuple[str, bool]]:
    """Return the set of unique seasonal item/base-shiny pairs for a player."""
    return {
        (item_name, shiny)
        for item_name, shiny, _rarity, _ts in iter_season_variants(player_data, exclude_limited=exclude_limited)
    }


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
