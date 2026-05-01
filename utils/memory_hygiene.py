"""Runtime memory hygiene helpers for long-lived bot processes."""

from __future__ import annotations

import ctypes
import gc
from typing import Any


def read_process_rss_mb() -> float | None:
    """Best-effort Linux RSS read without external dependencies."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("VmRSS:"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    return None
                return int(parts[1]) / 1024.0
    except Exception:
        return None

    return None


def _clear_lru_cache(func: Any, label: str, cleared: list[str]) -> None:
    cache_clear = getattr(func, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
        cleared.append(label)


def clear_known_caches() -> list[str]:
    """Clear selected process-local caches that are cheap to rebuild."""
    cleared: list[str] = []

    try:
        from utils.item_image_index import clear_item_image_index_cache

        clear_item_image_index_cache()
        cleared.append("item_image_index")
    except Exception:
        pass

    try:
        from utils.calc_points import _load_loot_entries, load_loot_points, load_loot_types

        _clear_lru_cache(_load_loot_entries, "calc_points._load_loot_entries", cleared)
        _clear_lru_cache(load_loot_points, "calc_points.load_loot_points", cleared)
        _clear_lru_cache(load_loot_types, "calc_points.load_loot_types", cleared)
    except Exception:
        pass

    try:
        from utils.loot_helpers.shareloot_image import clear_shareloot_image_caches

        clear_shareloot_image_caches()
        cleared.append("shareloot_image")
    except Exception:
        pass

    try:
        from utils.player_statistics import _load_item_to_dungeon

        _clear_lru_cache(_load_item_to_dungeon, "player_statistics._load_item_to_dungeon", cleared)
    except Exception:
        pass

    try:
        from utils.message_utils.loot_table_md_builder import load_dungeon_data

        _clear_lru_cache(load_dungeon_data, "loot_table_md_builder.load_dungeon_data", cleared)
    except Exception:
        pass

    try:
        from utils.set_operations import load_item_sets

        _clear_lru_cache(load_item_sets, "set_operations.load_item_sets", cleared)
    except Exception:
        pass

    return cleared


def malloc_trim() -> bool:
    """Ask glibc to return free heap memory to the OS when possible."""
    try:
        libc = ctypes.CDLL("libc.so.6")
        trim = getattr(libc, "malloc_trim", None)
        if trim is None:
            return False
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        return bool(trim(0))
    except Exception:
        return False


def run_memory_hygiene(
    *,
    clear_caches: bool = True,
    collect_garbage: bool = True,
    trim_allocator: bool = True,
) -> dict[str, Any]:
    """Run one memory-hygiene pass and return before/after telemetry."""
    rss_before = read_process_rss_mb()
    cleared_labels: list[str] = []
    gc_collected = 0
    trim_called = False
    trim_succeeded = False

    if clear_caches:
        cleared_labels = clear_known_caches()

    if collect_garbage:
        try:
            gc_collected = int(gc.collect())
        except Exception:
            gc_collected = 0

    if trim_allocator:
        trim_called = True
        trim_succeeded = malloc_trim()

    rss_after = read_process_rss_mb()
    delta = None
    if rss_before is not None and rss_after is not None:
        delta = float(rss_after - rss_before)

    return {
        "rss_before_mb": rss_before,
        "rss_after_mb": rss_after,
        "rss_delta_mb": delta,
        "cleared_caches": cleared_labels,
        "cleared_cache_count": len(cleared_labels),
        "gc_collected": gc_collected,
        "malloc_trim_called": trim_called,
        "malloc_trim_succeeded": trim_succeeded,
    }
