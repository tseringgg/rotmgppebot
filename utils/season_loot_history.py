from __future__ import annotations

from typing import Any, Dict, Iterable

from utils.item_log_timestamps import (
    now_unix_utc,
    parse_seasonal_item_variant_key,
    seasonal_item_key,
    seasonal_item_variant_key,
)

_ALLOWED_RARITIES = {"common", "uncommon", "rare", "legendary", "divine"}


def normalize_rarity(value: Any, fallback: str = "common") -> str:
    raw = str(value).strip().lower() if value is not None else ""
    if raw in _ALLOWED_RARITIES:
        return raw
    return fallback


def _rarity_rank(value: str) -> int:
    rarity = normalize_rarity(value)
    return {
        "common": 0,
        "uncommon": 1,
        "rare": 2,
        "legendary": 3,
        "divine": 4,
    }.get(rarity, 0)


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


def sync_legacy_season_fields(player_data: Any) -> None:
    history = _normalize_history_map(getattr(player_data, "season_item_history", {}))
    player_data.season_item_history = history

    unique_items: set[tuple[str, bool]] = set()
    season_item_rarities: Dict[str, str] = {}
    item_log_timestamps: Dict[str, int] = {}

    for variant_key, timestamps in history.items():
        parsed = parse_seasonal_item_variant_key(variant_key)
        if parsed is None:
            continue

        item_name, shiny, rarity = parsed
        base_key = seasonal_item_key(item_name, shiny)

        unique_items.add((item_name, shiny))

        current_rarity = season_item_rarities.get(base_key, "common")
        season_item_rarities[base_key] = rarity if _rarity_rank(rarity) >= _rarity_rank(current_rarity) else current_rarity

        if timestamps:
            last_ts = max(timestamps)
            previous_ts = item_log_timestamps.get(base_key, 0)
            if last_ts > previous_ts:
                item_log_timestamps[base_key] = last_ts

    player_data.unique_items = unique_items
    player_data.season_item_rarities = season_item_rarities
    player_data.item_log_timestamps = item_log_timestamps


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
    sync_legacy_season_fields(player_data)
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
        timestamps.pop()
        if timestamps:
            history[key] = timestamps
        else:
            history.pop(key, None)

    player_data.season_item_history = history
    sync_legacy_season_fields(player_data)
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
    sync_legacy_season_fields(player_data)
    return removed


def ensure_history_from_legacy(
    *,
    unique_items: Iterable[tuple[Any, Any]] | None,
    season_item_rarities: dict[str, Any] | None,
    item_log_timestamps: dict[str, Any] | None,
) -> Dict[str, list[int]]:
    history: Dict[str, list[int]] = {}
    rarity_lookup = season_item_rarities if isinstance(season_item_rarities, dict) else {}
    timestamp_lookup = item_log_timestamps if isinstance(item_log_timestamps, dict) else {}

    for raw_item in unique_items or []:
        if not isinstance(raw_item, (tuple, list)) or len(raw_item) < 2:
            continue
        item_name = str(raw_item[0]).strip()
        if not item_name:
            continue
        shiny = bool(raw_item[1])

        base_key = seasonal_item_key(item_name, shiny)
        rarity = normalize_rarity(rarity_lookup.get(base_key, "common"))
        ts_raw = timestamp_lookup.get(base_key)
        try:
            logged_at = int(ts_raw)
        except (TypeError, ValueError):
            logged_at = 0

        key = seasonal_item_variant_key(item_name, shiny, rarity)
        history[key] = [logged_at] if logged_at > 0 else []

    return _normalize_history_map(history)
