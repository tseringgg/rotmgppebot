"""Shared formatting and utility helpers for RealmShark menus."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_preview(token: str) -> str:
    if len(token) <= 10:
        return token
    return f"{token[:6]}...{token[-4:]}"


def format_points(points: float) -> str:
    return str(int(points)) if points == int(points) else f"{points:.1f}"


def build_pending_loot_summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No pending unmapped loot for this character yet."

    by_name: Dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        item_name = str(event.get("item_name", "")).strip() or "Unknown Item"
        by_name[item_name] = by_name.get(item_name, 0) + 1

    top_items = sorted(by_name.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    top_items_text = ", ".join(f"{name} x{count}" for name, count in top_items)

    recent_names: list[str] = []
    for event in events[-3:]:
        if not isinstance(event, dict):
            continue
        item_name = str(event.get("item_name", "")).strip() or "Unknown Item"
        recent_names.append(item_name)

    recent_text = ", ".join(recent_names) if recent_names else "None"
    return (
        f"{len(events)} pending drop(s). "
        f"Top loot: {top_items_text or 'None'}. "
        f"Most recent: {recent_text}."
    )
