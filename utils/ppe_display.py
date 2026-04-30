"""Facade for PPE display formatting.

Centralizes label formatting for PPE types so callers don't need to use
`utils.ppe_types` internals directly.
"""
from __future__ import annotations

from typing import Any

from utils.ppe_types import (
    normalize_ppe_type,
    ppe_type_compact_summary,
    ppe_type_display_from_options,
    ppe_type_option_signature,
)


def format_ppe_label_from_options(
    options: Any,
    *,
    compact: bool = False,
    guild_config: dict | None = None,
    fallback_type: Any = None,
) -> str:
    """Return a display label for the given PPE options.

    - `options` may be a normalized options dict or legacy value accepted by
      `utils.ppe_types`.
    - `compact` controls whether a short label is returned.
    - `guild_config` may contain a `ppe_settings` dict with overrides.
    - `fallback_type` is the legacy type string to use when needed.
    """
    ppe_settings = None
    if isinstance(guild_config, dict):
        raw = guild_config.get("ppe_settings", {})
        if isinstance(raw, dict):
            ppe_settings = raw

    return ppe_type_display_from_options(
        options,
        fallback_type=fallback_type,
        ppe_settings=ppe_settings,
        compact=compact,
    )


def format_ppe_label(ppe: Any, *, compact: bool = False, guild_config: dict | None = None) -> str:
    """Return a display label for a PPE object.

    The function will extract `ppe_type` and `ppe_type_options` from the
    provided object (or dict-like) and format the label consistently.
    """
    normalized = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    options = getattr(ppe, "ppe_type_options", None)
    return format_ppe_label_from_options(options, compact=compact, guild_config=guild_config, fallback_type=normalized)


def get_ppe_signature(options: Any, *, include_regular: bool = False) -> str:
    """Return the deterministic option signature for the provided options."""
    return ppe_type_option_signature(options, include_regular=include_regular)
