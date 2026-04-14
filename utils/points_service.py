"""Utilities for points service."""

import math
from typing import Any, Dict, Iterable

from dataclass import Bonus, Loot, PPEData
from utils.ppe_types import DEFAULT_PPE_TYPE_MULTIPLIERS, normalize_ppe_type, normalize_ppe_type_multipliers
from utils.calc_points import load_loot_points, load_loot_types, normalize_item_name
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
    ppe_settings = _get_ppe_settings(guild_config)
    normalized_multipliers = normalize_ppe_type_multipliers(ppe_settings.get("ppe_type_multipliers"))
    ppe_type = normalize_ppe_type(getattr(ppe, "ppe_type", None))
    return float(normalized_multipliers.get(ppe_type, DEFAULT_PPE_TYPE_MULTIPLIERS["regular"]))


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
    type_multiplier = get_ppe_type_multiplier_for_ppe(ppe, guild_config)
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
        "combined_item_multiplier": combined_multiplier,
    }


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
    value = base_points * _rarity_multiplier_for(effective_rarity, guild_config)
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
    final_points = base_points * _rarity_multiplier_for(effective_rarity, guild_config)

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


def recompute_ppe_points(ppe: PPEData, guild_config: Dict[str, Any] | None = None) -> Dict[str, float]:
    loot_points = load_loot_points()
    loot_total = 0.0

    for loot in ppe.loot:
        loot_total += calculate_item_points(
            item_name=loot.item_name,
            shiny=loot.shiny,
            quantity=loot.quantity,
            rarity=getattr(loot, "rarity", "common"),
            loot_points=loot_points,
            guild_config=guild_config,
        )

    bonus_total, penalty_total = split_bonus_points(ppe.bonuses)
    set_bonus_points = get_set_bonus_points_from_config(ppe, guild_config)
    modifier_bucket = get_effective_modifier_bucket_for_ppe(ppe, guild_config)
    penalty_breakdown = starting_penalty_breakdown_from_bonuses(ppe.bonuses, guild_config=guild_config)
    loot_adjustments = loot_adjustments_for_ppe(ppe, guild_config)

    adjusted_loot = _apply_percent(loot_total, float(modifier_bucket["loot_percent"]))
    adjusted_bonus = _apply_percent(bonus_total, float(modifier_bucket["bonus_percent"]))
    adjusted_penalty = sum(float(details["signed_adjusted_points"]) for details in penalty_breakdown.values())
    adjusted_penalty = _apply_percent(adjusted_penalty, float(modifier_bucket["penalty_percent"]))
    adjusted_loot = _apply_percent(adjusted_loot, float(modifier_bucket["total_percent"]))

    loot_after_item_multipliers = adjusted_loot * float(loot_adjustments["reduction_multiplier"])
    loot_after_item_multipliers *= float(loot_adjustments["type_multiplier"])

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
        "item_reduction_multiplier": round(float(loot_adjustments["reduction_multiplier"]), 4),
        "type_multiplier": round(float(loot_adjustments["type_multiplier"]), 4),
        "combined_item_multiplier": round(float(loot_adjustments["combined_item_multiplier"]), 4),
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
