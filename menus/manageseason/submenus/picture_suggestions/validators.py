"""Validation helpers for picture suggestions channel input."""

from __future__ import annotations

import re

_CHANNEL_ID_PATTERN = re.compile(r"<#(\d+)>|(\d+)")


def parse_channel_ids(raw_value: str) -> list[int]:
    """Parse channel mentions and IDs from user input into unique positive IDs."""
    text = str(raw_value or "").strip()
    if not text:
        raise ValueError(
            "ERROR: Provide at least one channel mention or channel ID (for example: `#season-loot` or `1234567890`)."
        )

    seen: set[int] = set()
    channel_ids: list[int] = []
    for match in _CHANNEL_ID_PATTERN.finditer(text):
        raw_id = match.group(1) or match.group(2)
        if raw_id is None:
            continue

        try:
            channel_id = int(raw_id)
        except ValueError:
            continue

        if channel_id <= 0 or channel_id in seen:
            continue

        seen.add(channel_id)
        channel_ids.append(channel_id)

    if not channel_ids:
        raise ValueError(
            "ERROR: I could not find valid channel mentions or channel IDs in your input."
        )

    return channel_ids
