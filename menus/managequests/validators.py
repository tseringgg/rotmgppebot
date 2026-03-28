"""CSV-backed validation for global quest item inputs."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from utils.calc_points import normalize_item_name

_LOOT_CSV = "rotmg_loot_drops_updated.csv"
_CATALOG_READY = False

_REGULAR_BY_NORM: dict[str, str] = {}
_SHINY_BY_NORM: dict[str, str] = {}
_SKIN_BY_NORM: dict[str, str] = {}


@dataclass(frozen=True)
class QuestValidationResult:
    valid_items: list[str]
    errors: list[str]


def _ensure_catalog() -> None:
    global _CATALOG_READY
    if _CATALOG_READY:
        return

    _REGULAR_BY_NORM.clear()
    _SHINY_BY_NORM.clear()
    _SKIN_BY_NORM.clear()

    with open(_LOOT_CSV, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            item_name = normalize_item_name(str(row.get("Item Name", "")).strip())
            loot_type = normalize_item_name(str(row.get("Loot Type", "")).strip()).lower()
            if not item_name:
                continue

            item_norm = item_name.lower()
            is_shiny_name = item_norm.endswith(" (shiny)")
            if loot_type == "skin":
                _SKIN_BY_NORM.setdefault(item_norm, item_name)
                continue
            if is_shiny_name:
                _SHINY_BY_NORM.setdefault(item_norm, item_name)
                continue

            _REGULAR_BY_NORM.setdefault(item_norm, item_name)

    _CATALOG_READY = True


def parse_item_input(raw_text: str) -> list[str]:
    parts = [segment.strip() for chunk in str(raw_text).splitlines() for segment in chunk.split(",")]
    return [item for item in parts if item]


def validate_items_for_category(category: str, raw_items: list[str]) -> QuestValidationResult:
    """
    Validate user-provided quest items against rotmg_loot_drops_updated.csv.

    Rules:
    - regular: valid spreadsheet item, not shiny, not skin
    - shiny: valid shiny item name (must include '(shiny)' in spreadsheet form)
    - skin: valid skin item name
    """
    _ensure_catalog()

    seen: set[str] = set()
    valid_items: list[str] = []
    errors: list[str] = []

    category_lower = category.strip().lower()
    for raw_item in raw_items:
        normalized_input = normalize_item_name(raw_item)
        norm = normalized_input.lower()
        if not normalized_input:
            continue
        if norm in seen:
            continue
        seen.add(norm)

        if category_lower == "regular":
            if norm.endswith(" (shiny)"):
                errors.append(f"• `{raw_item}` is shiny and cannot be added as a regular quest.")
                continue
            if norm in _SKIN_BY_NORM:
                errors.append(f"• `{raw_item}` is a skin and cannot be added as a regular quest.")
                continue
            canonical = _REGULAR_BY_NORM.get(norm)
            if not canonical:
                errors.append(f"• `{raw_item}` is not a valid regular item in `{_LOOT_CSV}`.")
                continue
            valid_items.append(canonical)
            continue

        if category_lower == "shiny":
            canonical = _SHINY_BY_NORM.get(norm)
            if not canonical:
                if not norm.endswith(" (shiny)") and f"{norm} (shiny)" in _SHINY_BY_NORM:
                    errors.append(f"• `{raw_item}` must be entered as `{normalized_input} (shiny)`.")
                else:
                    errors.append(f"• `{raw_item}` is not a valid shiny item in `{_LOOT_CSV}`.")
                continue
            valid_items.append(canonical)
            continue

        if category_lower == "skin":
            canonical = _SKIN_BY_NORM.get(norm)
            if not canonical:
                errors.append(f"• `{raw_item}` is not a valid skin item in `{_LOOT_CSV}`.")
                continue
            valid_items.append(canonical)
            continue

        raise ValueError(f"Unsupported quest category: {category}")

    return QuestValidationResult(valid_items=valid_items, errors=errors)
