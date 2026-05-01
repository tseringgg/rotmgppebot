"""Utilities for points service."""

from copy import deepcopy
import math
from typing import Any, Dict, Iterable

from dataclass import Bonus, Loot, PPEData
from utils.ppe_types import (
    DEFAULT_PPE_TYPE_MULTIPLIERS,
    get_ppe_type_multiplier_details_from_options,
    options_from_signature,
    normalize_ppe_type,
    normalize_ppe_type_multipliers,
    # compact summary formatting moved to display facade
    # keep normalize_ppe_type usage here
)
from utils.calc_points import load_loot_points, load_loot_types, normalize_item_name
from utils.ppe_display import format_ppe_label_from_options
from utils.guild_config import get_rarity_multipliers
from utils.loot_constants import normalize_rarity

PENALTY_NAMES = {
    "Pet Level Penalty",
    "Exalts Penalty",
    "Loot Boost Penalty",
    "In-Combat Reduction Penalty",
}

VALID_INCOMBAT_REDUCTION_OPTIONS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

DEFAULT_PENALTY_WEIGHTS = {
    "pet_level_per_point": 4.0,
    "exalts_per_point": 2.0,
    "loot_percent_per_point": 0.5,
    "incombat_seconds_per_point": 0.1,
}

MAX_PET_LEVEL = 100
MAX_EXALTS = 40
MAX_LOOT_BOOST = 25.0
MAX_INCOMBAT_REDUCTION = max(VALID_INCOMBAT_REDUCTION_OPTIONS)

PENALTY_COMPONENT_NAMES = {
    "pet": "Pet Level Penalty",
    "exalts": "Exalts Penalty",
    "loot": "Loot Boost Penalty",
    "incombat": "In-Combat Reduction Penalty",
}

POINT_MODIFIER_KEYS = (
    ("loot_percent", "loot"),
    ("bonus_percent", "bonus"),
    ("penalty_percent", "penalty"),
    ("total_percent", "total"),
)

STARTING_PENALTY_REDUCTION_KEYS = {
    "pet": "pet_level_percent_reduction",
    "exalts": "exalts_percent_reduction",
    "loot": "loot_percent_reduction",
    "incombat": "incombat_percent_reduction",
}


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _class_name_for_ppe(ppe: PPEData) -> str:
    class_name = getattr(ppe.name, "value", ppe.name)
    return str(class_name)


def _apply_percent(value: float, percent: float) -> float:
    return value * (1.0 + (percent / 100.0))


def _rarity_multiplier_for(value: Any, guild_config: Dict[str, Any] | None = None) -> float:
    rarity = normalize_rarity(value)
    multipliers = get_rarity_multipliers(guild_config or {})
    return float(multipliers.get(rarity, 1.0))


def _shiny_multiplier_for(shiny: bool, guild_config: Dict[str, Any] | None = None) -> float:
    if not shiny:
        return 1.0
    multipliers = get_rarity_multipliers(guild_config or {})
    return float(multipliers.get("shiny", 1.0))


def _item_multiplier_for(rarity: str, shiny: bool, guild_config: Dict[str, Any] | None = None) -> float:
    return _rarity_multiplier_for(rarity, guild_config) * _shiny_multiplier_for(shiny, guild_config)


def _get_points_settings(guild_config: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(guild_config, dict):
        return {}
    settings = guild_config.get("points_settings", {})
    return settings if isinstance(settings, dict) else {}


def _get_duplicate_point_reduction(guild_config: Dict[str, Any] | None) -> float:
    points_settings = _get_points_settings(guild_config)
    raw_value = points_settings.get("duplicate_point_reduction", 0.5)
    parsed = _as_float(raw_value, 0.5)
    return parsed if parsed >= 0 else 0.5


def _get_duplicate_match_mode(guild_config: Dict[str, Any] | None) -> str:
    points_settings = _get_points_settings(guild_config)
    mode = str(points_settings.get("duplicate_match_mode", "separate_rarity")).strip().lower()
    if mode in {"separate_rarity", "any_rarity", "non_divine_any_rarity", "all_including_shiny"}:
        return mode
    return "separate_rarity"


def _get_ppe_settings(guild_config: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(guild_config, dict):
        return {}
    settings = guild_config.get("ppe_settings", {})
    return settings if isinstance(settings, dict) else {}


def _get_starting_penalty_modifiers(guild_config: Dict[str, Any] | None) -> Dict[str, float]:
    points_settings = _get_points_settings(guild_config)
    raw_modifiers = (
        points_settings.get("starting_penalty_modifiers", {})
        if isinstance(points_settings.get("starting_penalty_modifiers", {}), dict)
        else {}
    )

    return {
        "pet": max(0.0, _as_float(raw_modifiers.get(STARTING_PENALTY_REDUCTION_KEYS["pet"]), 0.0)),
        "exalts": max(0.0, _as_float(raw_modifiers.get(STARTING_PENALTY_REDUCTION_KEYS["exalts"]), 0.0)),
        "loot": max(0.0, _as_float(raw_modifiers.get(STARTING_PENALTY_REDUCTION_KEYS["loot"]), 0.0)),
        "incombat": max(0.0, _as_float(raw_modifiers.get(STARTING_PENALTY_REDUCTION_KEYS["incombat"]), 0.0)),
    }


def get_ppe_type_multiplier_for_ppe(
    ppe: PPEData,
    guild_config: Dict[str, Any] | None = None,
) -> float:
    details = get_ppe_type_multiplier_details_for_ppe(ppe, guild_config)
    return float(details["multiplier"])


def get_ppe_type_multiplier_details_for_ppe(
    ppe: PPEData,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ppe_settings = _get_ppe_settings(guild_config)
    raw_options = getattr(ppe, "ppe_type_options", None)

    if isinstance(raw_options, dict) and raw_options:
        details = get_ppe_type_multiplier_details_from_options(
            raw_options,
            ppe_settings,
            current_type=getattr(ppe, "ppe_type", None),
        )
        return {
            "multiplier": float(details["multiplier"]),
            "source": str(details.get("source", "base")),
            "signature": str(details.get("signature", "legacy")),
            "legacy_type": details.get("legacy_type"),
            "components": list(details.get("components", [])),
            "component_lines": list(details.get("component_lines", [])),
        }

    ppe_type = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    normalized_multipliers = normalize_ppe_type_multipliers(ppe_settings.get("ppe_type_multipliers"))
    return {
        "multiplier": float(normalized_multipliers.get(ppe_type, DEFAULT_PPE_TYPE_MULTIPLIERS["regular"])),
        "source": "legacy",
        "signature": "legacy",
        "legacy_type": ppe_type,
        "components": [],
        "component_lines": [],
    }


def _get_penalty_weights(guild_config: Dict[str, Any] | None) -> Dict[str, float]:
    points_settings = _get_points_settings(guild_config)
    raw_weights = points_settings.get("penalty_weights", {}) if isinstance(points_settings.get("penalty_weights", {}), dict) else {}

    def _non_negative_float(key: str, fallback: float) -> float:
        parsed = _as_float(raw_weights.get(key), fallback)
        return parsed if parsed >= 0 else fallback

    return {
        "pet_level_per_point": _non_negative_float("pet_level_per_point", DEFAULT_PENALTY_WEIGHTS["pet_level_per_point"]),
        "exalts_per_point": _non_negative_float("exalts_per_point", DEFAULT_PENALTY_WEIGHTS["exalts_per_point"]),
        "loot_percent_per_point": _non_negative_float("loot_percent_per_point", DEFAULT_PENALTY_WEIGHTS["loot_percent_per_point"]),
        "incombat_seconds_per_point": _non_negative_float("incombat_seconds_per_point", DEFAULT_PENALTY_WEIGHTS["incombat_seconds_per_point"]),
    }


def _get_tops_point_mode(guild_config: Dict[str, Any] | None) -> str:
    points_settings = _get_points_settings(guild_config)
    mode = str(points_settings.get("tops_point_mode", "current")).strip().lower()
    if mode in {"current", "once", "none"}:
        return mode
    return "current"


def _normalize_item_key(item_name: str, shiny: bool) -> str:
    normalized_item = normalize_item_name(item_name)
    return f"{normalized_item} (shiny)" if shiny else normalized_item


def _duplicate_bucket_key(item_name: str, shiny: bool, rarity: str, mode: str) -> tuple[Any, ...] | None:
    normalized_item = normalize_item_name(item_name).lower()
    normalized_rarity = normalize_rarity(rarity)

    if mode == "all_including_shiny":
        return (normalized_item,)
    if mode == "any_rarity":
        return (normalized_item, bool(shiny))
    if mode == "non_divine_any_rarity":
        if normalized_rarity == "divine":
            return None
        return (normalized_item, bool(shiny))
    return (normalized_item, bool(shiny), normalized_rarity)


def _is_tops_item(item_name: str, shiny: bool = False) -> bool:
    loot_types = load_loot_types()
    lookup = _normalize_item_key(item_name, shiny)
    loot_type = loot_types.get(lookup)
    if loot_type is None and shiny:
        loot_type = loot_types.get(normalize_item_name(item_name))
    return str(loot_type).strip().lower() == "tops"


def _get_modifier_bucket(points_settings: Dict[str, Any], class_name: str) -> Dict[str, float | None]:
    global_settings = points_settings.get("global", {}) if isinstance(points_settings.get("global", {}), dict) else {}
    class_overrides = points_settings.get("class_overrides", {}) if isinstance(points_settings.get("class_overrides", {}), dict) else {}
    class_settings = class_overrides.get(class_name, {}) if isinstance(class_overrides.get(class_name, {}), dict) else {}

    return {
        "loot_percent": _as_float(global_settings.get("loot_percent", 0.0)) + _as_float(class_settings.get("loot_percent", 0.0)),
        "bonus_percent": _as_float(global_settings.get("bonus_percent", 0.0)) + _as_float(class_settings.get("bonus_percent", 0.0)),
        "penalty_percent": _as_float(global_settings.get("penalty_percent", 0.0)) + _as_float(class_settings.get("penalty_percent", 0.0)),
        "total_percent": _as_float(global_settings.get("total_percent", 0.0)) + _as_float(class_settings.get("total_percent", 0.0)),
        "minimum_total": class_settings.get("minimum_total"),
    }


def apply_percent_modifier(value: float, percent: float) -> float:
    """Apply a percent modifier to a value."""
    return _apply_percent(float(value), _as_float(percent))


def get_effective_modifier_bucket_for_class(
    class_name: str,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float | None]:
    """Return the effective global+class modifier bucket for a class."""
    points_settings = _get_points_settings(guild_config)
    return _get_modifier_bucket(points_settings, class_name)


def get_effective_modifier_bucket_for_ppe(
    ppe: PPEData,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float | None]:
    """Return the effective global+class modifier bucket for a PPE."""
    return get_effective_modifier_bucket_for_class(_class_name_for_ppe(ppe), guild_config)


def get_starting_penalty_modifiers_for_guild(guild_config: Dict[str, Any] | None = None) -> Dict[str, float]:
    """Return the configured percent reductions for starting penalty components."""
    return _get_starting_penalty_modifiers(guild_config)


def _is_non_default_percent(value: Any) -> bool:
    return abs(_as_float(value, 0.0)) > 1e-9


def _format_signed_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _modifier_parts_from_bucket(bucket: Dict[str, Any]) -> list[str]:
    parts: list[str] = []
    for key, label in POINT_MODIFIER_KEYS:
        percent = _as_float(bucket.get(key), 0.0)
        if _is_non_default_percent(percent):
            parts.append(f"{label} {_format_signed_percent(percent)}")

    minimum_total = bucket.get("minimum_total")
    if minimum_total is not None:
        parts.append(f"minimum total {_as_float(minimum_total, 0.0):.2f}")
    return parts


def _starting_penalty_breakdown_from_raw_components(
    raw_components: Dict[str, float],
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, float]]:
    breakdown: Dict[str, Dict[str, float]] = {}

    for component_key, label in PENALTY_COMPONENT_NAMES.items():
        # Accept either canonical keys (pet/exalts/loot/incombat) or bonus-name keys.
        raw_value = raw_components.get(component_key, raw_components.get(label, 0.0))
        raw_points = abs(_as_float(raw_value, 0.0))
        reduction_percent = 0.0
        adjusted_points = raw_points
        breakdown[label] = {
            "raw_points": raw_points,
            "reduction_percent": reduction_percent,
            "reduction_points": raw_points - adjusted_points,
            "adjusted_points": adjusted_points,
            "signed_adjusted_points": -adjusted_points,
        }

    return breakdown


def _clamp_penalty_inputs(*, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float) -> Dict[str, float]:
    return {
        "pet_level": float(min(MAX_PET_LEVEL, max(0, int(pet_level)))),
        "num_exalts": float(min(MAX_EXALTS, max(0, int(num_exalts)))),
        "percent_loot": float(min(MAX_LOOT_BOOST, max(0.0, float(percent_loot)))),
        "incombat_reduction": float(min(MAX_INCOMBAT_REDUCTION, max(0.0, float(incombat_reduction)))),
    }


def compute_item_reduction_percent_from_inputs(
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    guild_config: Dict[str, Any] | None = None,
) -> float:
    """Return additive item-point reduction percent from starting-penalty inputs.

    Each configured modifier is interpreted as percent item reduction per unit of that
    starting stat (pet level, exalts, loot boost percent, and in-combat seconds).
    """
    modifiers = _get_starting_penalty_modifiers(guild_config)
    reduction_percent = (
        max(0, int(pet_level)) * modifiers["pet"]
        + max(0, int(num_exalts)) * modifiers["exalts"]
        + max(0.0, float(percent_loot)) * modifiers["loot"]
        + max(0.0, float(incombat_reduction)) * modifiers["incombat"]
    )
    return min(100.0, max(0.0, reduction_percent))


def compute_item_reduction_breakdown_from_inputs(
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    """Return contribution percentages for each starting-stat reduction input."""
    modifiers = _get_starting_penalty_modifiers(guild_config)
    pet_contribution = max(0, int(pet_level)) * modifiers["pet"]
    exalts_contribution = max(0, int(num_exalts)) * modifiers["exalts"]
    loot_contribution = max(0.0, float(percent_loot)) * modifiers["loot"]
    incombat_contribution = max(0.0, float(incombat_reduction)) * modifiers["incombat"]
    uncapped_total = pet_contribution + exalts_contribution + loot_contribution + incombat_contribution
    capped_total = min(100.0, max(0.0, uncapped_total))
    return {
        "pet_reduction_percent": pet_contribution,
        "exalts_reduction_percent": exalts_contribution,
        "loot_reduction_percent": loot_contribution,
        "incombat_reduction_percent": incombat_contribution,
        "uncapped_total_reduction_percent": uncapped_total,
        "total_reduction_percent": capped_total,
    }


def compute_item_reduction_percent_from_bonuses(
    bonuses: Iterable[Bonus],
    guild_config: Dict[str, Any] | None = None,
) -> float:
    inputs = penalty_inputs_from_bonuses(bonuses, guild_config=guild_config)
    return compute_item_reduction_percent_from_inputs(
        int(inputs["pet_level"]),
        int(inputs["num_exalts"]),
        float(inputs["percent_loot"]),
        float(inputs["incombat_reduction"]),
        guild_config=guild_config,
    )


def compute_item_reduction_breakdown_from_bonuses(
    bonuses: Iterable[Bonus],
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    inputs = penalty_inputs_from_bonuses(bonuses, guild_config=guild_config)
    return compute_item_reduction_breakdown_from_inputs(
        int(inputs["pet_level"]),
        int(inputs["num_exalts"]),
        float(inputs["percent_loot"]),
        float(inputs["incombat_reduction"]),
        guild_config=guild_config,
    )


def compute_item_reduction_multiplier_from_bonuses(
    bonuses: Iterable[Bonus],
    guild_config: Dict[str, Any] | None = None,
) -> float:
    reduction_percent = compute_item_reduction_percent_from_bonuses(bonuses, guild_config=guild_config)
    return max(0.0, 1.0 - (reduction_percent / 100.0))


def loot_adjustments_for_ppe(
    ppe: PPEData,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    """Return item-only multipliers and reduction details for a PPE."""
    inputs = penalty_inputs_from_bonuses(ppe.bonuses, guild_config=guild_config)
    reduction_breakdown = compute_item_reduction_breakdown_from_inputs(
        int(inputs["pet_level"]),
        int(inputs["num_exalts"]),
        float(inputs["percent_loot"]),
        float(inputs["incombat_reduction"]),
        guild_config=guild_config,
    )
    reduction_percent = float(reduction_breakdown["total_reduction_percent"])
    reduction_multiplier = max(0.0, 1.0 - (reduction_percent / 100.0))
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    loot_multiplier = apply_percent_modifier(1.0, _as_float(modifier_bucket.get("loot_percent"), 0.0))
    total_multiplier = apply_percent_modifier(1.0, _as_float(modifier_bucket.get("total_percent"), 0.0))
    multiplier_details = get_ppe_type_multiplier_details_for_ppe(ppe, guild_config)
    type_multiplier = float(multiplier_details["multiplier"])
    combined_multiplier = reduction_multiplier * loot_multiplier * total_multiplier * type_multiplier
    return {
        "pet_reduction_percent": float(reduction_breakdown["pet_reduction_percent"]),
        "exalts_reduction_percent": float(reduction_breakdown["exalts_reduction_percent"]),
        "loot_reduction_percent": float(reduction_breakdown["loot_reduction_percent"]),
        "incombat_reduction_percent": float(reduction_breakdown["incombat_reduction_percent"]),
        "total_reduction_percent": reduction_percent,
        "reduction_multiplier": reduction_multiplier,
        "loot_percent_multiplier": loot_multiplier,
        "total_percent_multiplier": total_multiplier,
        "type_multiplier": type_multiplier,
        "type_multiplier_source": str(multiplier_details.get("source", "legacy")),
        "type_multiplier_signature": str(multiplier_details.get("signature", "legacy")),
        "type_multiplier_component_lines": list(multiplier_details.get("component_lines", [])),
        "combined_item_multiplier": combined_multiplier,
    }


def _format_multiplier(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded)}x"
    return f"{rounded:.2f}".rstrip("0").rstrip(".") + "x"


def loot_adjustment_detail_lines(loot_adjustments: Dict[str, Any]) -> list[str]:
    lines: list[str] = []

    component_rows = (
        ("pet_reduction_percent", "Pet Level"),
        ("exalts_reduction_percent", "Exalts"),
        ("loot_reduction_percent", "Loot Boost"),
        ("incombat_reduction_percent", "In-Combat Reduction"),
    )

    for key, label in component_rows:
        percent = _as_float(loot_adjustments.get(key), 0.0)
        if abs(percent) <= 1e-9:
            continue
        multiplier = max(0.0, 1.0 - (percent / 100.0))
        lines.append(f"{label}: -{percent:.2f}% ({_format_multiplier(multiplier)})")

    total_reduction_percent = _as_float(loot_adjustments.get("total_reduction_percent"), 0.0)
    if abs(total_reduction_percent) > 1e-9:
        reduction_multiplier = _as_float(loot_adjustments.get("reduction_multiplier"), 1.0)
        lines.append(f"Stat Reduction: -{total_reduction_percent:.2f}% ({_format_multiplier(reduction_multiplier)})")

    type_multiplier = _as_float(loot_adjustments.get("type_multiplier"), 1.0)
    type_source = str(loot_adjustments.get("type_multiplier_source", "")).strip().lower()
    type_signature = str(loot_adjustments.get("type_multiplier_signature", "")).strip()
    type_summary = ""
    if type_signature and type_signature != "legacy":
        options = options_from_signature(type_signature)
        if options is not None:
            type_summary = format_ppe_label_from_options(options, compact=True)

    if type_summary:
        if type_source == "preset":
            lines.append(f"Type Multiplier ({type_summary}): {type_multiplier:.2f} (overridden)")
        else:
            lines.append(f"Type Multiplier ({type_summary}): {_format_multiplier(type_multiplier)}")
    else:
        if type_source == "preset":
            lines.append(f"Type Multiplier: {type_multiplier:.2f} (overridden)")
        else:
            lines.append(f"Type Multiplier: {_format_multiplier(type_multiplier)}")

    type_component_lines = loot_adjustments.get("type_multiplier_component_lines", [])
    if isinstance(type_component_lines, list):
        for raw_line in type_component_lines:
            detail = str(raw_line or "").strip()
            if detail:
                lines.append(f"  - {detail}")

    combined_multiplier = _as_float(loot_adjustments.get("combined_item_multiplier"), 1.0)
    lines.append(f"Combined Multiplier: {_format_multiplier(combined_multiplier)}")

    return lines


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def format_starting_penalty_line(
    label: str,
    value_text: str,
    details: Dict[str, float],
    *,
    bold_values: bool = True,
) -> str:
    """Format a single starting-penalty line for embeds and markdown exports."""
    final_points = _format_points(_as_float(details.get("signed_adjusted_points"), 0.0))
    reduction_percent = _as_float(details.get("reduction_percent"), 0.0)
    if bold_values:
        line = f"{label}: **{value_text}** -> **{final_points}** Points"
    else:
        line = f"{label}: {value_text} -> {final_points} Points"
    if reduction_percent > 0:
        line += f" (-{reduction_percent:g}% Item Points)"
    return line


def starting_penalty_breakdown_from_inputs(
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, float]]:
    raw_components = compute_penalty_components(
        pet_level,
        num_exalts,
        percent_loot,
        incombat_reduction,
        guild_config=guild_config,
    )
    return _starting_penalty_breakdown_from_raw_components(raw_components, guild_config=guild_config)


def starting_penalty_breakdown_from_bonuses(
    bonuses: Iterable[Bonus],
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, float]]:
    raw_components = penalty_map_from_bonuses(bonuses)
    return _starting_penalty_breakdown_from_raw_components(raw_components, guild_config=guild_config)


def non_default_points_adjustment_lines(
    guild_config: Dict[str, Any] | None,
    *,
    class_names: Iterable[str] | None = None,
) -> list[str]:
    """Describe point adjustments that differ from defaults for markdown reporting."""
    points_settings = _get_points_settings(guild_config)
    global_settings = points_settings.get("global", {}) if isinstance(points_settings.get("global", {}), dict) else {}
    class_overrides = (
        points_settings.get("class_overrides", {})
        if isinstance(points_settings.get("class_overrides", {}), dict)
        else {}
    )

    lines: list[str] = []

    global_parts = _modifier_parts_from_bucket(global_settings)
    if global_parts:
        lines.append(f"- Global: {', '.join(global_parts)}")

    if class_names is None:
        selected_classes = sorted(
            [str(name) for name in class_overrides.keys() if isinstance(name, str)],
            key=lambda name: name.lower(),
        )
    else:
        selected_classes = sorted(
            {str(name) for name in class_names if str(name).strip()},
            key=lambda name: name.lower(),
        )

    for class_name in selected_classes:
        override = class_overrides.get(class_name, {})
        if not isinstance(override, dict):
            continue

        class_parts = _modifier_parts_from_bucket(override)
        if class_parts:
            lines.append(f"- {class_name}: {', '.join(class_parts)}")

    return lines


def get_item_base_points(item_name: str, shiny: bool, loot_points: Dict[str, float] | None = None) -> float:
    points_map = loot_points or load_loot_points()
    normalized_item = normalize_item_name(item_name)
    lookup = f"{normalized_item} (shiny)" if shiny else normalized_item
    return float(points_map.get(lookup, 0.0))


def has_item_variant(item_name: str, shiny: bool, loot_points: Dict[str, float] | None = None) -> bool:
    points_map = loot_points or load_loot_points()
    normalized_item = normalize_item_name(item_name)
    lookup = f"{normalized_item} (shiny)" if shiny else normalized_item
    return lookup in points_map


def calculate_drop_points(
    item_name: str,
    shiny: bool,
    rarity: str = "common",
    loot_points: Dict[str, float] | None = None,
    guild_config: Dict[str, Any] | None = None,
) -> float:
    base_points = get_item_base_points(item_name, shiny, loot_points=loot_points)
    if base_points <= 0:
        return 0.0

    effective_rarity = normalize_rarity(rarity)
    value = base_points * _item_multiplier_for(effective_rarity, shiny, guild_config)
    return math.floor(value * 2) / 2


def calculate_item_points(
    item_name: str,
    shiny: bool,
    quantity: int,
    rarity: str = "common",
    loot_points: Dict[str, float] | None = None,
    guild_config: Dict[str, Any] | None = None,
) -> float:
    base_points = get_item_base_points(item_name, shiny, loot_points=loot_points)
    if base_points <= 0:
        return 0.0

    quantity = max(0, int(quantity))
    if quantity <= 0:
        return 0.0

    effective_rarity = normalize_rarity(rarity)
    final_points = base_points * _item_multiplier_for(effective_rarity, shiny, guild_config)

    if _is_tops_item(item_name, shiny):
        tops_mode = _get_tops_point_mode(guild_config)
        if tops_mode == "none":
            return 0.0
        if tops_mode == "once":
            return final_points

    if quantity == 1:
        return final_points

    duplicate_reduction = _get_duplicate_point_reduction(guild_config)
    return final_points + (final_points * duplicate_reduction * (quantity - 1))


def calculate_bonus_points(bonus: Bonus) -> float:
    quantity = max(1, int(getattr(bonus, "quantity", 1)))
    return float(bonus.points) * quantity


def split_bonus_points(bonuses: Iterable[Bonus]) -> tuple[float, float]:
    """Split bonuses into (regular_bonus_points, penalty_points).
    
    Excludes "Set Completion Bonus" from regular bonuses since set points
    should not be affected by bonus modifiers.
    """
    normal_bonus_points = 0.0
    penalty_points = 0.0

    for bonus in bonuses:
        total = calculate_bonus_points(bonus)
        if bonus.name in PENALTY_NAMES:
            penalty_points += total
        elif bonus.name != "Set Completion Bonus":  # Exclude set bonuses from regular bonus calculation
            normal_bonus_points += total

    return normal_bonus_points, penalty_points


def get_set_bonus_points(bonuses: Iterable[Bonus]) -> float:
    """Get total points from Set Completion Bonus entries.
    
    Set points should not be affected by bonus modifiers, so we calculate
    them separately and add them directly to the total.
    """
    set_bonus_points = 0.0
    for bonus in bonuses:
        if bonus.name == "Set Completion Bonus":
            set_bonus_points += calculate_bonus_points(bonus)
    return set_bonus_points

def get_set_bonus_points_from_config(ppe: PPEData, guild_config: Dict[str, Any] | None = None) -> float:
    """Calculate set bonus points based on completed sets and current guild overrides.
    
    This recalculates from current guild config rather than using stale stored values.
    Set points should not be affected by bonus modifiers, so we return them directly.
    """
    if not guild_config:
        guild_config = {}
    
    from utils.guild_config import get_set_bonuses
    from utils.set_operations import load_item_sets
    
    completed_sets = getattr(ppe, "completed_sets", []) or []
    if not completed_sets:
        return 0.0
    
    set_bonuses = get_set_bonuses(guild_config)
    all_sets = load_item_sets()
    
    total_set_bonus = 0.0
    for set_name in completed_sets:
        if set_name in all_sets:
            set_type = all_sets[set_name].get("type", "").upper()
            if set_type in set_bonuses and set_name in set_bonuses[set_type]:
                total_set_bonus += set_bonuses[set_type][set_name]
    
    return total_set_bonus


def compute_effective_ppe_points(
    ppe: PPEData,
    guild_config: Dict[str, Any] | None = None,
) -> float:
    """Compute points for a PPE using current config without mutating the original object."""
    try:
        ppe_copy = deepcopy(ppe)
    except Exception:
        return _as_float(getattr(ppe, "points", 0.0), 0.0)

    breakdown = recompute_ppe_points(ppe_copy, guild_config)
    return _as_float(breakdown.get("total", getattr(ppe_copy, "points", 0.0)), 0.0)


def recompute_ppe_points(ppe: PPEData, guild_config: Dict[str, Any] | None = None) -> Dict[str, float]:
    loot_points = load_loot_points()
    loot_total = 0.0

    duplicate_reduction = _get_duplicate_point_reduction(guild_config)
    duplicate_mode = _get_duplicate_match_mode(guild_config)
    tops_mode = _get_tops_point_mode(guild_config)

    drop_events: list[tuple[int, int, int, Loot]] = []
    fallback_sequence = 0

    for entry_index, loot in enumerate(ppe.loot):
        try:
            quantity = max(0, int(getattr(loot, "quantity", 0)))
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            continue

        parsed_times: list[int] = []
        for raw_ts in getattr(loot, "logged_times", []):
            try:
                parsed = int(raw_ts)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                parsed_times.append(parsed)
        parsed_times.sort()

        for event_index in range(quantity):
            if event_index < len(parsed_times):
                timestamp = parsed_times[event_index]
                sort_group = 0
            else:
                fallback_sequence += 1
                timestamp = fallback_sequence
                sort_group = 1
            drop_events.append((sort_group, timestamp, entry_index, loot))

    drop_events.sort(key=lambda row: (row[0], row[1], row[2]))

    duplicate_counts: dict[tuple[Any, ...], int] = {}
    tops_seen: set[tuple[str, bool, str]] = set()

    for _sort_group, _timestamp, _entry_index, loot in drop_events:
        item_name = str(getattr(loot, "item_name", ""))
        shiny = bool(getattr(loot, "shiny", False))
        rarity = normalize_rarity(getattr(loot, "rarity", "common"))

        base_points = get_item_base_points(item_name, shiny, loot_points=loot_points)
        if base_points <= 0:
            continue

        final_points = base_points * _item_multiplier_for(rarity, shiny, guild_config)

        if _is_tops_item(item_name, shiny):
            tops_key = (normalize_item_name(item_name).lower(), shiny, rarity)
            if tops_mode == "none":
                continue
            if tops_mode == "once":
                if tops_key in tops_seen:
                    continue
                tops_seen.add(tops_key)

        duplicate_key = _duplicate_bucket_key(item_name, shiny, rarity, duplicate_mode)
        if duplicate_key is None:
            loot_total += final_points
            continue

        seen_count = duplicate_counts.get(duplicate_key, 0)
        if seen_count <= 0:
            loot_total += final_points
        else:
            loot_total += final_points * duplicate_reduction
        duplicate_counts[duplicate_key] = seen_count + 1

    bonus_total, penalty_total = split_bonus_points(ppe.bonuses)
    set_bonus_points = get_set_bonus_points_from_config(ppe, guild_config)
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    penalty_breakdown = starting_penalty_breakdown_from_bonuses(ppe.bonuses, guild_config=guild_config)
    loot_adjustments = loot_adjustments_for_ppe(ppe, guild_config)

    # Coerce modifier bucket values defensively to avoid TypeError on bad config
    loot_percent_val = _as_float(modifier_bucket.get("loot_percent"), 0.0)
    bonus_percent_val = _as_float(modifier_bucket.get("bonus_percent"), 0.0)
    penalty_percent_val = _as_float(modifier_bucket.get("penalty_percent"), 0.0)
    total_percent_val = _as_float(modifier_bucket.get("total_percent"), 0.0)

    adjusted_loot = _apply_percent(loot_total, loot_percent_val)
    adjusted_bonus = _apply_percent(bonus_total, bonus_percent_val)
    adjusted_penalty = sum(_as_float(details.get("signed_adjusted_points"), 0.0) for details in penalty_breakdown.values())
    adjusted_penalty = _apply_percent(adjusted_penalty, penalty_percent_val)
    adjusted_loot = _apply_percent(adjusted_loot, total_percent_val)

    loot_after_item_multipliers = adjusted_loot * _as_float(loot_adjustments.get("reduction_multiplier"), 1.0)
    loot_after_item_multipliers *= _as_float(loot_adjustments.get("type_multiplier"), 1.0)

    subtotal_before_item_multipliers = adjusted_loot + adjusted_bonus + adjusted_penalty
    # Set points are added directly without any modifiers
    total = loot_after_item_multipliers + adjusted_bonus + adjusted_penalty + set_bonus_points

    minimum_total = modifier_bucket.get("minimum_total")
    if minimum_total is not None:
        min_points = _as_float(minimum_total, fallback=0.0)
        total = max(total, min_points)

    ppe.points = round(total, 2)
    return {
        "loot_raw": round(loot_total, 2),
        "loot_after_item_reduction": round(loot_after_item_multipliers, 2),
        "loot_after_item_multipliers": round(loot_after_item_multipliers, 2),
        "bonus_raw": round(bonus_total, 2),
        "bonus_after_modifiers": round(adjusted_bonus, 2),
        "penalty_raw": round(penalty_total, 2),
        "penalty_after_modifiers": round(adjusted_penalty, 2),
        "set_bonus_raw": round(set_bonus_points, 2),
        "subtotal_before_item_reduction": round(subtotal_before_item_multipliers, 2),
        "item_reduction_multiplier": round(_as_float(loot_adjustments.get("reduction_multiplier"), 1.0), 4),
        "type_multiplier": round(_as_float(loot_adjustments.get("type_multiplier"), 1.0), 4),
        "combined_item_multiplier": round(_as_float(loot_adjustments.get("combined_item_multiplier"), 1.0), 4),
        "total": ppe.points,
    }


def parse_penalty_inputs(
    pet_level: int | str,
    num_exalts: int | str,
    percent_loot: float | str,
    incombat_reduction: float | str,
) -> tuple[Dict[str, float | int] | None, str | None]:
    try:
        parsed_pet_level = int(str(pet_level).strip())
        parsed_num_exalts = int(str(num_exalts).strip())
        parsed_percent_loot = float(str(percent_loot).strip())
        parsed_incombat_reduction = float(str(incombat_reduction).strip())
    except (TypeError, ValueError):
        return None, "❌ Invalid values. Use numbers for all fields."

    error = validate_penalty_inputs(parsed_pet_level, parsed_num_exalts, parsed_percent_loot, parsed_incombat_reduction)
    if error:
        return None, error

    return {
        "pet_level": parsed_pet_level,
        "num_exalts": parsed_num_exalts,
        "percent_loot": parsed_percent_loot,
        "incombat_reduction": parsed_incombat_reduction,
    }, None


def compute_penalty_components(
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    weights = _get_penalty_weights(guild_config)
    pet_weight = weights["pet_level_per_point"]
    exalts_weight = weights["exalts_per_point"]
    loot_weight = weights["loot_percent_per_point"]
    incombat_weight = weights["incombat_seconds_per_point"]
    return {
        PENALTY_COMPONENT_NAMES["pet"]: 0.0 if pet_weight <= 0 else -round(pet_level / pet_weight),
        PENALTY_COMPONENT_NAMES["exalts"]: 0.0 if exalts_weight <= 0 else -(num_exalts / exalts_weight),
        PENALTY_COMPONENT_NAMES["loot"]: 0.0 if loot_weight <= 0 else -(percent_loot / loot_weight),
        PENALTY_COMPONENT_NAMES["incombat"]: 0.0 if incombat_weight <= 0 else -(incombat_reduction / incombat_weight),
    }


def penalty_map_from_bonuses(bonuses: Iterable[Bonus]) -> Dict[str, float]:
    result = {
        "pet": 0.0,
        "exalts": 0.0,
        "loot": 0.0,
        "incombat": 0.0,
    }

    for bonus in bonuses:
        total = calculate_bonus_points(bonus)
        if bonus.name == PENALTY_COMPONENT_NAMES["pet"]:
            result["pet"] += total
        elif bonus.name == PENALTY_COMPONENT_NAMES["exalts"]:
            result["exalts"] += total
        elif bonus.name == PENALTY_COMPONENT_NAMES["loot"]:
            result["loot"] += total
        elif bonus.name == PENALTY_COMPONENT_NAMES["incombat"]:
            result["incombat"] += total

    return result


def penalty_inputs_from_bonuses(
    bonuses: Iterable[Bonus],
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    penalties = penalty_map_from_bonuses(bonuses)
    weights = _get_penalty_weights(guild_config)

    pet_weight = weights["pet_level_per_point"]
    exalts_weight = weights["exalts_per_point"]
    loot_weight = weights["loot_percent_per_point"]
    incombat_weight = weights["incombat_seconds_per_point"]

    pet_level = int(round(-pet_weight * penalties["pet"])) if penalties["pet"] != 0 and pet_weight > 0 else 0
    exalts = int(round(-exalts_weight * penalties["exalts"])) if penalties["exalts"] != 0 and exalts_weight > 0 else 0
    loot_boost = round(-loot_weight * penalties["loot"], 1) if penalties["loot"] != 0 and loot_weight > 0 else 0.0
    incombat = round(-incombat_weight * penalties["incombat"], 1) if penalties["incombat"] != 0 and incombat_weight > 0 else 0.0

    return _clamp_penalty_inputs(
        pet_level=pet_level,
        num_exalts=exalts,
        percent_loot=loot_boost,
        incombat_reduction=incombat,
    )


def build_penalty_bonuses(components: Dict[str, float]) -> list[Bonus]:
    penalties: list[Bonus] = []
    for name, points in components.items():
        if points == 0:
            continue
        penalties.append(Bonus(name=name, points=points, repeatable=False, quantity=1))
    return penalties


def apply_penalties_to_ppe(
    ppe: PPEData,
    pet_level: int,
    num_exalts: int,
    percent_loot: float,
    incombat_reduction: float,
    guild_config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    components = compute_penalty_components(
        pet_level,
        num_exalts,
        percent_loot,
        incombat_reduction,
        guild_config=guild_config,
    )
    new_penalties = build_penalty_bonuses(components)

    removed_penalty_points = 0.0
    kept_bonuses: list[Bonus] = []
    for bonus in ppe.bonuses:
        if bonus.name in PENALTY_NAMES:
            removed_penalty_points += calculate_bonus_points(bonus)
        else:
            kept_bonuses.append(bonus)

    ppe.bonuses = kept_bonuses + new_penalties
    new_penalty_points = sum(calculate_bonus_points(bonus) for bonus in new_penalties)

    return {
        "components": components,
        "new_penalties": new_penalties,
        "removed_penalty_points": round(removed_penalty_points, 2),
        "new_penalty_points": round(new_penalty_points, 2),
    }


def validate_penalty_inputs(pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float) -> str | None:
    if not (0 <= pet_level <= 100):
        return "❌ Pet level must be between `0` and `100`."
    if not (0 <= num_exalts <= 40):
        return "❌ Number of exalts must be between `0` and `40`."
    if not (0.0 <= percent_loot <= 25.0):
        return "❌ Percent loot boost must be between `0%` and `25%`."
    if incombat_reduction not in set(VALID_INCOMBAT_REDUCTION_OPTIONS):
        return "❌ In-combat damage reduction must be one of: `0`, `0.2`, `0.4`, `0.6`, `0.8`, `1.0`."
    return None
