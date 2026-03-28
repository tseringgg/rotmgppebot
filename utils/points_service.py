import math
from typing import Any, Dict, Iterable

from dataclass import Bonus, Loot, PPEData
from utils.calc_points import load_loot_points, normalize_item_name

PENALTY_NAMES = {
    "Pet Level Penalty",
    "Exalts Penalty",
    "Loot Boost Penalty",
    "In-Combat Reduction Penalty",
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


def _get_points_settings(guild_config: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(guild_config, dict):
        return {}
    settings = guild_config.get("points_settings", {})
    return settings if isinstance(settings, dict) else {}


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


def get_item_base_points(item_name: str, shiny: bool, loot_points: Dict[str, float] | None = None) -> float:
    points_map = loot_points or load_loot_points()
    normalized_item = normalize_item_name(item_name)
    lookup = f"{normalized_item} (shiny)" if shiny else normalized_item
    return float(points_map.get(lookup, 0.0))


def calculate_drop_points(item_name: str, divine: bool, shiny: bool, loot_points: Dict[str, float] | None = None) -> float:
    base_points = get_item_base_points(item_name, shiny, loot_points=loot_points)
    if base_points <= 0:
        return 0.0

    value = base_points * (2 if divine else 1)
    return math.floor(value * 2) / 2


def calculate_item_points(item_name: str, divine: bool, shiny: bool, quantity: int, loot_points: Dict[str, float] | None = None) -> float:
    base_points = get_item_base_points(item_name, shiny, loot_points=loot_points)
    if base_points <= 0:
        return 0.0

    final_points = base_points * (2 if divine else 1)
    if quantity > 1 and final_points > 1:
        return final_points + (math.floor(final_points) / 2) * (quantity - 1)
    return final_points * quantity


def calculate_bonus_points(bonus: Bonus) -> float:
    quantity = max(1, int(getattr(bonus, "quantity", 1)))
    return float(bonus.points) * quantity


def split_bonus_points(bonuses: Iterable[Bonus]) -> tuple[float, float]:
    normal_bonus_points = 0.0
    penalty_points = 0.0

    for bonus in bonuses:
        total = calculate_bonus_points(bonus)
        if bonus.name in PENALTY_NAMES:
            penalty_points += total
        else:
            normal_bonus_points += total

    return normal_bonus_points, penalty_points


def recompute_ppe_points(ppe: PPEData, guild_config: Dict[str, Any] | None = None) -> Dict[str, float]:
    loot_points = load_loot_points()
    loot_total = 0.0

    for loot in ppe.loot:
        loot_total += calculate_item_points(
            item_name=loot.item_name,
            divine=loot.divine,
            shiny=loot.shiny,
            quantity=loot.quantity,
            loot_points=loot_points,
        )

    bonus_total, penalty_total = split_bonus_points(ppe.bonuses)
    points_settings = _get_points_settings(guild_config)
    modifier_bucket = _get_modifier_bucket(points_settings, _class_name_for_ppe(ppe))

    adjusted_loot = _apply_percent(loot_total, float(modifier_bucket["loot_percent"]))
    adjusted_bonus = _apply_percent(bonus_total, float(modifier_bucket["bonus_percent"]))
    adjusted_penalty = _apply_percent(penalty_total, float(modifier_bucket["penalty_percent"]))
    total = adjusted_loot + adjusted_bonus + adjusted_penalty
    total = _apply_percent(total, float(modifier_bucket["total_percent"]))

    minimum_total = modifier_bucket.get("minimum_total")
    if minimum_total is not None:
        min_points = _as_float(minimum_total, fallback=0.0)
        total = max(total, min_points)

    ppe.points = round(total, 2)
    return {
        "loot_raw": round(loot_total, 2),
        "bonus_raw": round(bonus_total, 2),
        "penalty_raw": round(penalty_total, 2),
        "total": ppe.points,
    }


def compute_penalty_components(pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float) -> Dict[str, float]:
    return {
        "Pet Level Penalty": -round(pet_level / 4),
        "Exalts Penalty": -0.5 * num_exalts,
        "Loot Boost Penalty": -2 * percent_loot,
        "In-Combat Reduction Penalty": -(2 * (incombat_reduction / 0.2)),
    }


def build_penalty_bonuses(components: Dict[str, float]) -> list[Bonus]:
    penalties: list[Bonus] = []
    for name, points in components.items():
        if points == 0:
            continue
        penalties.append(Bonus(name=name, points=points, repeatable=False, quantity=1))
    return penalties


def apply_penalties_to_ppe(ppe: PPEData, pet_level: int, num_exalts: int, percent_loot: float, incombat_reduction: float) -> Dict[str, Any]:
    components = compute_penalty_components(pet_level, num_exalts, percent_loot, incombat_reduction)
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
    if incombat_reduction not in {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}:
        return "❌ In-combat damage reduction must be one of: `0`, `0.2`, `0.4`, `0.6`, `0.8`, `1`."
    return None
