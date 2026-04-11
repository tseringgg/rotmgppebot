from __future__ import annotations

from datetime import datetime, timezone

from utils.calc_points import normalize_item_name


def now_unix_utc() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def seasonal_item_key(item_name: str, shiny: bool) -> str:
    normalized = normalize_item_name(item_name)
    return f"{normalized}|{1 if shiny else 0}"


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
