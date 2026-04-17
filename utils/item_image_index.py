"""Shared item image index helpers."""

from __future__ import annotations

import glob
import os
from functools import lru_cache

from utils.calc_points import normalize_item_name


_DEFAULT_DUNGEONS_PATH = os.path.join("helper_pics", "dungeon_pics")


def _normalized_lookup_key(path: str) -> str:
    base_name = os.path.splitext(os.path.basename(path))[0]
    return normalize_item_name(base_name).lower()


@lru_cache(maxsize=4)
def _build_item_image_index(dungeons_path: str) -> dict[str, str]:
    index: dict[str, str] = {}
    pattern = os.path.join(dungeons_path, "**", "*.png")

    for png_file in glob.glob(pattern, recursive=True):
        normalized = _normalized_lookup_key(png_file)
        if normalized and normalized not in index:
            index[normalized] = png_file

    return index


def get_item_image_index(dungeons_path: str | None = None) -> dict[str, str]:
    resolved_path = os.path.normpath(dungeons_path or _DEFAULT_DUNGEONS_PATH)
    return _build_item_image_index(resolved_path)


def clear_item_image_index_cache() -> None:
    _build_item_image_index.cache_clear()
